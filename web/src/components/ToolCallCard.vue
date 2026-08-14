<script setup lang="ts">
import { computed } from "vue";
import type { ChatItem } from "../types";

const props = defineProps<{
  item: Extract<ChatItem, { kind: "tool" }>;
}>();

const argsText = computed(() => JSON.stringify(props.item.args, null, 2));
</script>

<template>
  <details class="tool-card" :class="{ 'tool-error': item.isError }">
    <summary>
      <span class="tool-name">🔧 {{ item.name }}</span>
      <span v-if="item.pending" class="tool-status pending">执行中…</span>
      <span v-else-if="item.isError" class="tool-status error">失败</span>
      <span v-else class="tool-status ok">完成</span>
    </summary>
    <div class="tool-body">
      <div class="tool-section">
        <div class="tool-label">参数</div>
        <pre>{{ argsText }}</pre>
      </div>
      <div v-if="item.output !== undefined" class="tool-section">
        <div class="tool-label">结果</div>
        <pre>{{ item.output }}</pre>
      </div>
    </div>
  </details>
</template>
