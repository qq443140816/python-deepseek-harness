<script setup lang="ts">
/*
 * Copyright (c) 2026 redfox <591006133@qq.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

import { computed, nextTick, ref, watch } from "vue";
import ToolCallCard from "./ToolCallCard.vue";
import type { ChatItem } from "../types";

const props = defineProps<{
  items: ChatItem[];
  streaming: boolean;
}>();

const emit = defineEmits<{
  (e: "send", content: string): void;
  (e: "answer", callId: string, answer: string): void;
}>();

const input = ref("");
const answerDraft = ref("");
const scroller = ref<HTMLElement | null>(null);

const pendingAsk = computed(() =>
  props.items.find(
    (i): i is Extract<ChatItem, { kind: "ask" }> =>
      i.kind === "ask" && !i.answered,
  ),
);

watch(
  () => props.items.length,
  async () => {
    await nextTick();
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight });
  },
);

function send(): void {
  const content = input.value.trim();
  if (!content || props.streaming) {
    return;
  }
  input.value = "";
  emit("send", content);
}

function answer(): void {
  const text = answerDraft.value.trim();
  if (!text || !pendingAsk.value) {
    return;
  }
  answerDraft.value = "";
  emit("answer", pendingAsk.value.callId, text);
}
</script>

<template>
  <div class="chat">
    <div ref="scroller" class="chat-scroll">
      <template v-for="(item, index) in items" :key="index">
        <div v-if="item.kind === 'user'" class="msg msg-user">
          <div class="bubble bubble-user">{{ item.content }}</div>
        </div>
        <div v-else-if="item.kind === 'assistant'" class="msg msg-assistant">
          <div class="bubble bubble-assistant">{{ item.content }}</div>
        </div>
        <details v-else-if="item.kind === 'thinking'" class="thinking">
          <summary>思考过程</summary>
          <pre>{{ item.content }}</pre>
        </details>
        <ToolCallCard v-else-if="item.kind === 'tool'" :item="item" />
        <div v-else-if="item.kind === 'ask'" class="ask-card">
          <div class="ask-question">🙋 {{ item.question }}</div>
          <div v-if="item.answered" class="ask-answer">
            已回复：{{ item.answer }}
          </div>
          <div v-else class="ask-input-row">
            <input
              v-model="answerDraft"
              placeholder="输入你的回答…"
              @keydown.enter="answer"
            />
            <button @click="answer">回复</button>
          </div>
        </div>
        <div v-else class="msg msg-error">⚠️ {{ item.message }}</div>
      </template>
      <div v-if="streaming" class="streaming-hint">正在生成…</div>
    </div>
    <div class="composer">
      <textarea
        v-model="input"
        rows="2"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        :disabled="streaming"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button :disabled="streaming || !input.trim()" @click="send">
        发送
      </button>
    </div>
  </div>
</template>
