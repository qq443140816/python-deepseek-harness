<script setup lang="ts">
import { onMounted, ref } from "vue";
import SessionSidebar from "./components/SessionSidebar.vue";
import ChatView from "./components/ChatView.vue";
import {
  createSession,
  deleteSession,
  getSession,
  listSessions,
  respondAskUser,
  streamMessage,
} from "./api";
import type { ChatItem, SessionEvent, SessionInfo, StreamEvent } from "./types";

const sessions = ref<SessionInfo[]>([]);
const currentId = ref<string | null>(null);
const items = ref<ChatItem[]>([]);
const streaming = ref(false);
const errorMsg = ref("");
/** 当前正在累积的增量块类型（assistant/thinking），用于合并 delta。 */
let accumulating: "assistant" | "thinking" | null = null;

onMounted(loadSessions);

async function loadSessions(): Promise<void> {
  sessions.value = await listSessions();
}

async function onCreate(): Promise<void> {
  const session = await createSession();
  await loadSessions();
  await onSelect(session.id);
}

async function onSelect(id: string): Promise<void> {
  currentId.value = id;
  errorMsg.value = "";
  const detail = await getSession(id);
  items.value = eventsToItems(detail.events);
}

async function onDelete(id: string): Promise<void> {
  await deleteSession(id);
  if (currentId.value === id) {
    currentId.value = null;
    items.value = [];
  }
  await loadSessions();
}

async function onSend(content: string): Promise<void> {
  if (!currentId.value || streaming.value) {
    return;
  }
  streaming.value = true;
  errorMsg.value = "";
  items.value.push({ kind: "user", content });
  try {
    await streamMessage(currentId.value, content, onStreamEvent);
  } catch (err) {
    errorMsg.value = `请求失败：${String(err)}`;
  } finally {
    streaming.value = false;
  }
}

async function onAnswer(callId: string, answer: string): Promise<void> {
  if (!currentId.value) {
    return;
  }
  const result = await respondAskUser(currentId.value, answer);
  if (result.resolved) {
    const ask = items.value.find(
      (i): i is Extract<ChatItem, { kind: "ask" }> =>
        i.kind === "ask" && i.callId === callId,
    );
    if (ask) {
      ask.answered = true;
      ask.answer = answer;
    }
  } else {
    errorMsg.value = "该问题已不在等待状态";
  }
}

function onStreamEvent(ev: StreamEvent): void {
  const list = items.value;
  switch (ev.type) {
    case "text_delta":
      if (accumulating === "assistant") {
        const last = list[list.length - 1] as Extract<
          ChatItem,
          { kind: "assistant" }
        >;
        last.content += ev.delta;
      } else {
        list.push({ kind: "assistant", content: ev.delta });
        accumulating = "assistant";
      }
      break;
    case "thinking_delta":
      if (accumulating === "thinking") {
        const last = list[list.length - 1] as Extract<
          ChatItem,
          { kind: "thinking" }
        >;
        last.content += ev.delta;
      } else {
        list.push({ kind: "thinking", content: ev.delta });
        accumulating = "thinking";
      }
      break;
    case "tool_call":
      accumulating = null;
      if (ev.name !== "ask_user") {
        list.push({
          kind: "tool",
          callId: ev.call_id,
          name: ev.name,
          args: ev.arguments,
          isError: false,
          pending: true,
        });
      }
      break;
    case "ask_user":
      accumulating = null;
      list.push({
        kind: "ask",
        callId: ev.call_id,
        question: ev.question,
        answered: false,
      });
      break;
    case "tool_result": {
      accumulating = null;
      const tool = list.find(
        (i): i is Extract<ChatItem, { kind: "tool" }> =>
          i.kind === "tool" && i.callId === ev.call_id,
      );
      if (tool) {
        tool.output = ev.output;
        tool.isError = ev.is_error;
        tool.pending = false;
      } else {
        const ask = list.find(
          (i): i is Extract<ChatItem, { kind: "ask" }> =>
            i.kind === "ask" && i.callId === ev.call_id,
        );
        if (ask) {
          ask.answered = true;
          ask.answer = ev.output;
        }
      }
      break;
    }
    case "error":
      accumulating = null;
      list.push({ kind: "error", message: ev.message });
      break;
    case "done":
      accumulating = null;
      break;
  }
}

/** 把会话事件流映射为聊天渲染项。 */
function eventsToItems(events: SessionEvent[]): ChatItem[] {
  const result: ChatItem[] = [];
  for (const ev of events) {
    const payload = ev.payload as Record<string, never> & {
      content?: string;
      calls?: Array<{
        id: string;
        name: string;
        arguments: Record<string, unknown>;
      }>;
      call_id?: string;
      output?: string;
      is_error?: boolean;
    };
    if (ev.type === "user") {
      result.push({ kind: "user", content: payload.content ?? "" });
    } else if (ev.type === "assistant") {
      result.push({ kind: "assistant", content: payload.content ?? "" });
    } else if (ev.type === "thinking") {
      result.push({ kind: "thinking", content: payload.content ?? "" });
    } else if (ev.type === "tool_call") {
      for (const call of payload.calls ?? []) {
        if (call.name === "ask_user") {
          result.push({
            kind: "ask",
            callId: call.id,
            question: String(call.arguments?.question ?? ""),
            answered: false,
          });
        } else {
          result.push({
            kind: "tool",
            callId: call.id,
            name: call.name,
            args: call.arguments ?? {},
            isError: false,
            pending: true,
          });
        }
      }
    } else if (ev.type === "tool_result") {
      const tool = result.find(
        (i): i is Extract<ChatItem, { kind: "tool" }> =>
          i.kind === "tool" && i.callId === payload.call_id,
      );
      if (tool) {
        tool.output = payload.output ?? "";
        tool.isError = payload.is_error ?? false;
        tool.pending = false;
      } else {
        const ask = result.find(
          (i): i is Extract<ChatItem, { kind: "ask" }> =>
            i.kind === "ask" && i.callId === payload.call_id,
        );
        if (ask) {
          ask.answered = true;
          ask.answer = payload.output ?? "";
        }
      }
    } else if (ev.type === "system_note") {
      result.push({ kind: "error", message: payload.content ?? "" });
    }
  }
  return result;
}
</script>

<template>
  <div class="layout">
    <SessionSidebar
      :sessions="sessions"
      :current-id="currentId"
      @create="onCreate"
      @select="onSelect"
      @delete="onDelete"
    />
    <main class="main">
      <ChatView
        v-if="currentId"
        :items="items"
        :streaming="streaming"
        @send="onSend"
        @answer="onAnswer"
      />
      <div v-else class="empty">
        <h1>python-deepseek-harness</h1>
        <p>企业自研通用 Agent 框架 · 新建一个会话开始对话</p>
      </div>
      <p v-if="errorMsg" class="global-error">{{ errorMsg }}</p>
    </main>
  </div>
</template>
