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

/** 会话概要（与后端 SessionOut 对应，ID 为字符串）。 */
export interface SessionInfo {
  id: string;
  title: string;
  revision: number;
  created_time: string;
  updated_time: string;
}

/** 会话事件（与后端 EventOut 对应）。 */
export interface SessionEvent {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  created_time: string;
}

export interface SessionDetail {
  session: SessionInfo;
  events: SessionEvent[];
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

/** 聊天流渲染项。 */
export type ChatItem =
  | { kind: "user"; content: string }
  | { kind: "assistant"; content: string }
  | { kind: "thinking"; content: string }
  | {
      kind: "tool";
      callId: string;
      name: string;
      args: Record<string, unknown>;
      output?: string;
      isError: boolean;
      pending: boolean;
    }
  | {
      kind: "ask";
      callId: string;
      question: string;
      answered: boolean;
      answer?: string;
    }
  | { kind: "error"; message: string };

/** SSE 事件（后端 LoopEvent 序列化结果）。 */
export type StreamEvent =
  | { type: "text_delta"; delta: string }
  | { type: "thinking_delta"; delta: string }
  | {
      type: "tool_call";
      call_id: string;
      name: string;
      arguments: Record<string, unknown>;
    }
  | {
      type: "tool_result";
      call_id: string;
      name: string;
      output: string;
      is_error: boolean;
    }
  | { type: "ask_user"; call_id: string; question: string }
  | { type: "done"; content: string }
  | { type: "error"; message: string };
