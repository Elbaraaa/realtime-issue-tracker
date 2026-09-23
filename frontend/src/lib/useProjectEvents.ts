import { useEffect, useRef, useState } from "react";
import { getToken } from "./api";

export interface ProjectEvent {
  type: "activity";
  id: number;
  kind: string;
  issue_id: number | null;
  actor_id: number;
  data: Record<string, unknown>;
  created_at: string;
}

const CLOSE_UNAUTHORIZED = 4401;
const CLOSE_FORBIDDEN = 4403;
const MAX_BACKOFF_MS = 30_000;

export function backoffDelay(attempt: number): number {
  return Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt);
}

/**
 * Subscribes to a project's live activity. `onEvent` gets each event; `onReady` fires on
 * every (re)connect so callers can refetch anything they missed while offline.
 */
export function useProjectEvents(
  projectId: number,
  handlers: { onEvent: (event: ProjectEvent) => void; onReady: () => void },
): boolean {
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    let socket: WebSocket | null = null;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    function connect() {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/api/ws/projects/${projectId}`);
      socket.onopen = () => socket?.send(JSON.stringify({ token: getToken() }));
      socket.onmessage = (message) => {
        const data = JSON.parse(message.data as string);
        if (data.type === "ready") {
          attempt = 0;
          setConnected(true);
          handlersRef.current.onReady();
        } else if (data.type === "activity") {
          handlersRef.current.onEvent(data as ProjectEvent);
        }
      };
      socket.onclose = (event) => {
        setConnected(false);
        if (stopped || event.code === CLOSE_UNAUTHORIZED || event.code === CLOSE_FORBIDDEN) return;
        timer = setTimeout(connect, backoffDelay(attempt++));
      };
    }

    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [projectId]);

  return connected;
}
