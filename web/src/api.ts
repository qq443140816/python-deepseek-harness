import type {
  SessionDetail,
  SessionInfo,
  StreamEvent,
  ToolInfo,
} from "./types";

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export function listSessions(): Promise<SessionInfo[]> {
  return fetch("/api/sessions").then((r) => json<SessionInfo[]>(r));
}

export function createSession(title = ""): Promise<SessionInfo> {
  return fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  }).then((r) => json<SessionInfo>(r));
}

export function getSession(id: string): Promise<SessionDetail> {
  return fetch(`/api/sessions/${id}`).then((r) => json<SessionDetail>(r));
}

export function deleteSession(id: string): Promise<void> {
  return fetch(`/api/sessions/${id}`, { method: "DELETE" }).then((r) => {
    if (!r.ok && r.status !== 204) {
      throw new Error(`HTTP ${r.status}`);
    }
  });
}

export function listTools(): Promise<ToolInfo[]> {
  return fetch("/api/tools").then((r) => json<ToolInfo[]>(r));
}

export function respondAskUser(
  sessionId: string,
  answer: string,
): Promise<{ resolved: boolean }> {
  return fetch(`/api/sessions/${sessionId}/responses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  }).then((r) => json<{ resolved: boolean }>(r));
}

/** 发送消息并消费 SSE 事件流。 */
export async function streamMessage(
  sessionId: string,
  content: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const resp = await fetch(`/api/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      for (const line of frame.split("\n")) {
        if (line.startsWith("data: ")) {
          onEvent(JSON.parse(line.slice(6)) as StreamEvent);
        }
      }
    }
  }
}
