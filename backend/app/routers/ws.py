import asyncio
import contextlib
from collections.abc import Callable

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..db import get_session_factory
from ..events import hub
from ..models import Membership
from ..security import decode_token

router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 5
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403


def _is_member(factory: Callable[[], Session], project_id: int, user_id: int) -> bool:
    with factory() as db:
        return db.get(Membership, (project_id, user_id)) is not None


@router.websocket("/ws/projects/{project_id}")
async def project_events(
    websocket: WebSocket,
    project_id: int,
    factory: Callable[[], Session] = Depends(get_session_factory),
):
    """Streams a project's activity. The client authenticates with its first message,
    {"token": "<jwt>"}, which keeps tokens out of URLs and proxy access logs."""
    await websocket.accept()
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        with contextlib.suppress(RuntimeError):
            await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    token = hello.get("token") if isinstance(hello, dict) else None
    user_id = decode_token(token) if isinstance(token, str) else None
    if user_id is None:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    if not await run_in_threadpool(_is_member, factory, project_id, user_id):
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    queue = hub.subscribe(project_id)

    async def forward() -> None:
        while True:
            await websocket.send_json(await queue.get())

    sender = asyncio.create_task(forward())
    try:
        await websocket.send_json({"type": "ready"})
        while True:
            # Clients don't send anything after auth; this just notices disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        hub.unsubscribe(project_id, queue)
