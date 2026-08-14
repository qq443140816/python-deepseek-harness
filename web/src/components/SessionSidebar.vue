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

import type { SessionInfo } from "../types";

defineProps<{
  sessions: SessionInfo[];
  currentId: string | null;
}>();

const emit = defineEmits<{
  (e: "create"): void;
  (e: "select", id: string): void;
  (e: "delete", id: string): void;
}>();

function formatTime(value: string): string {
  const date = new Date(value);
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`;
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-header">
      <span class="brand">pdsh</span>
      <button class="btn-new" title="新建会话" @click="emit('create')">
        ＋ 新建
      </button>
    </div>
    <ul class="session-list">
      <li
        v-for="session in sessions"
        :key="session.id"
        :class="{ active: session.id === currentId }"
        @click="emit('select', session.id)"
      >
        <div class="session-title">
          {{ session.title || `会话 ${session.id.slice(-6)}` }}
        </div>
        <div class="session-meta">
          <span>{{ formatTime(session.updated_time) }}</span>
          <button
            class="btn-del"
            title="删除会话"
            @click.stop="emit('delete', session.id)"
          >
            删除
          </button>
        </div>
      </li>
      <li v-if="sessions.length === 0" class="session-empty">
        暂无会话
      </li>
    </ul>
  </aside>
</template>
