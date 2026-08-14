<script setup lang="ts">
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
