"""In-process pub/sub that fans project events out to connected WebSockets.

Request handlers run in a worker thread, so publishing hands each event to the
subscriber's own event loop with call_soon_threadsafe. This works for a single
API process; running several replicas would need a shared channel such as
Postgres LISTEN/NOTIFY or Redis, behind the same publish/subscribe interface.
"""

import asyncio
import contextlib
import threading
from collections import defaultdict
from typing import Any

from .models import ActivityEvent

_QUEUE_SIZE = 256


class Hub:
    def __init__(self) -> None:
        self._subs: dict[int, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(
            set
        )
        self._lock = threading.Lock()

    def subscribe(self, project_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
        with self._lock:
            self._subs[project_id].add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, project_id: int, queue: asyncio.Queue) -> None:
        with self._lock:
            subs = self._subs.get(project_id, set())
            subs -= {s for s in subs if s[1] is queue}
            if not subs:
                self._subs.pop(project_id, None)

    def publish(self, project_id: int, event: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subs.get(project_id, ()))
        for loop, queue in subs:
            loop.call_soon_threadsafe(_offer, queue, event)


def _offer(queue: asyncio.Queue, event: dict[str, Any]) -> None:
    # A stalled client falls behind; it resyncs from the REST API on reconnect.
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(event)


hub = Hub()


def publish_activity(*events: ActivityEvent) -> None:
    for ev in events:
        hub.publish(
            ev.project_id,
            {
                "type": "activity",
                "id": ev.id,
                "kind": ev.kind,
                "issue_id": ev.issue_id,
                "actor_id": ev.actor_id,
                "data": ev.data,
                "created_at": ev.created_at.isoformat(),
            },
        )
