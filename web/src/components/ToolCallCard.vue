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
