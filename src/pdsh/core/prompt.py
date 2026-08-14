# Copyright (c) 2026 redfox <591006133@qq.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""系统提示词组装（对齐 dsh system-prompt 包）。

基础人设 + 时间上下文 + 工具使用指引；不含任何代码专用能力描述。
"""

from __future__ import annotations

from datetime import datetime

_BASE_PERSONA = """\
你是由企业自研 Agent 框架 python-deepseek-harness（pdsh）驱动的通用 AI 助手。

工作准则：
1. 面向任务：先理解用户目标，再行动；复杂任务用 todo_write 列清单跟踪。
2. 善用工具：需要外部信息或执行动作时调用对应工具，不要凭空编造结果。
3. 需要用户决策或补充信息时，用 ask_user 提问，一次只问一个关键问题。
4. 输出简洁、结构化，直接给结论与依据，避免空话。"""

_TOOL_GUIDANCE = """\
可用工具：{tools}。
调用约定：参数必须符合工具 Schema；工具失败时先依据错误信息调整重试，\
多次失败则如实告知用户。"""


def build_system_prompt(
    *,
    tool_names: list[str],
    now: datetime | None = None,
) -> str:
    """组装系统提示词。

    tool_names 为空时省略工具指引段落。
    """
    moment = now or datetime.now()
    parts = [
        _BASE_PERSONA,
        f"当前时间：{moment:%Y-%m-%d %H:%M}（{moment:%A}）。",
    ]
    if tool_names:
        parts.append(_TOOL_GUIDANCE.format(tools=", ".join(sorted(tool_names))))
    return "\n\n".join(parts)
