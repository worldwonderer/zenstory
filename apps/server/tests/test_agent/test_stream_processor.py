"""Regression tests for the file-streaming state machine."""

from agent.core.stream_processor import (
    BUFFER_MAX_SIZE,
    StreamProcessor,
    StreamState,
)


def _drive(chunks):
    """Feed chunks to a fresh processor in WAITING_START; return (results, proc)."""
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    results = [proc.process_content(c) for c in chunks]
    return results, proc


def _all_conversation(results):
    return "".join(
        r.conversation_content + r.conversation_content_after_file for r in results
    )


def test_canonical_marker_in_one_chunk():
    results, _ = _drive(["<file>hello world</file>"])
    assert any(r.file_complete for r in results)
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "hello world"
    assert "hello world" not in _all_conversation(results)


def test_uppercase_start_marker_split_across_chunks_is_detected():
    # "<FILE>" split as "<FI" + "LE>" must still route the body into the file,
    # not the chat transcript (the per-chunk normalize alone could not see it).
    results, proc = _drive(["<FI", "LE>hello", "</file>"])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "hello"
    assert "hello" not in _all_conversation(results)


def test_whitespace_end_marker_split_across_chunks_is_detected():
    results, proc = _drive(["<file>body text", "< /fil", "e >tail"])
    completed = next((r for r in results if r.file_complete), None)
    assert completed is not None
    assert completed.final_content == "body text"
    # Trailing text after the (variant) end marker is normal conversation.
    assert _all_conversation(results).endswith("tail")


def test_overflow_drains_tail_instead_of_leaking_to_chat():
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    proc.process_content("<file>")

    big = "x" * (BUFFER_MAX_SIZE + 100)
    overflow = proc.process_content(big)
    assert overflow.file_complete is True
    assert overflow.buffer_exceeded is True
    assert proc.state == StreamState.DRAINING

    # The still-streaming remainder of the oversized body must be swallowed.
    tail = proc.process_content("LEAKED_TAIL_SHOULD_NOT_APPEAR")
    assert tail.conversation_content == ""

    # Content after the closing marker resumes as normal conversation.
    closing = proc.process_content("</file>after the file")
    assert proc.state == StreamState.IDLE
    assert closing.conversation_content == "after the file"
    assert "LEAKED_TAIL" not in closing.conversation_content


def test_stream_end_while_draining_discards_tail():
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    proc.process_content("<file>")
    proc.process_content("x" * (BUFFER_MAX_SIZE + 100))
    assert proc.state == StreamState.DRAINING
    proc.process_content("unterminated overflow tail")
    final = proc.finalize_on_stream_end()
    assert final.conversation_content == ""
    assert proc.state == StreamState.IDLE


def test_inline_code_end_marker_in_body_is_content():
    # 正文里用行内代码讨论 `</file>` 不能提前结束文件：
    # 截断的文件 + 剩余正文/真实结束标记泄漏进对话流。
    results, proc = _drive([
        "<file>",
        "正文第一段。用法示例：`</file>` 表示结束。",
        "后半部分正文",
        "</file>",
    ])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "正文第一段。用法示例：`</file>` 表示结束。后半部分正文"
    assert _all_conversation(results) == ""


def test_fenced_code_end_marker_in_body_is_content():
    body = "第一段\n```\n</file>\n```\n第二段"
    results, proc = _drive(["<file>" + body, "</file>"])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == body
    assert _all_conversation(results) == ""


def test_fenced_code_end_marker_survives_flush_boundary():
    # 围栏开口先被 flush 出 temp_buffer，之后才出现 </file>：
    # 围栏开合状态必须跨 flush 保留，否则围栏内的字面量被当成真实标记。
    head = "A" * 100 + "\n```python\n"
    body = head + "x" * 100 + "\n</file> 还在代码块里\n" + "```\n尾段"
    results, proc = _drive([
        "<file>" + head,
        "x" * 100 + "\n</file> 还在代码块里\n",
        "```\n尾段",
        "</file>",
    ])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == body
    assert _all_conversation(results) == ""


def test_inline_code_start_marker_in_narration_does_not_start_file():
    # 叙述里行内代码 `<file>` 不是真实开始标记；真实标记随后到达时，
    # 前面的叙述应作为对话输出，文件内容从真实标记之后开始。
    results, proc = _drive([
        "我会用 `<file>` 标记开始输出。",
        "<file>正文",
        "</file>",
    ])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "正文"
    convo = _all_conversation(results)
    assert "`<file>`" in convo
    assert "正文" not in convo


def test_backtick_and_end_marker_arriving_in_separate_chunks():
    # 行内代码的反引号与 </file> 分属不同 chunk，重组后仍应识别为字面量
    results, proc = _drive([
        "<file>用法：`",
        "</file>",
        "` 表示结束。正文继续",
        "</file>",
    ])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "用法：`</file>` 表示结束。正文继续"
    assert _all_conversation(results) == ""


def test_pending_inline_backtick_resolves_to_real_marker():
    # 反引号后紧跟 </file>，但下一个字符不是反引号 -> 是真实结束标记
    results, proc = _drive(["<file>末尾带`", "</file>", "后记"])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "末尾带`"
    assert _all_conversation(results) == "后记"


def test_pending_inline_backtick_resolves_real_at_stream_end():
    # 流结束时反引号不会再闭合，挂起的 </file> 应按真实结束标记处理
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    proc.process_content("<file>正文`")
    proc.process_content("</file>")
    final = proc.finalize_on_stream_end()
    assert final.file_complete is True
    assert final.final_content == "正文`"
    assert proc.state == StreamState.IDLE


def test_unclosed_fence_before_real_start_marker_resolves_at_stream_end():
    # 叙述里出现一个未闭合的 ```：开始标记在流结束前始终无法判定（围栏可能
    # 在后续 chunk 闭合）。流结束时围栏不会再闭合，必须按 at_eof 语义复扫，
    # 正文写入文件，而不是把带 <file> 原始标记的整段正文倒进聊天。
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    results = [
        proc.process_content("好的，输出格式```\n"),
        proc.process_content("<file>这是正文第一段。"),
        proc.process_content("</file>已完成。"),
    ]
    final = proc.finalize_on_stream_end()
    assert final.file_complete is True
    assert final.final_content == "这是正文第一段。"
    convo = _all_conversation([*results, final])
    assert convo == "好的，输出格式```\n已完成。"
    assert "<file>" not in convo
    assert proc.state == StreamState.IDLE


def test_fence_wrapped_file_block_is_written_at_stream_end():
    # 模型把整块 <file>…</file> 包在 ``` 围栏里输出（提示词范例本身就是这种
    # 写法）：围栏保护让开始标记全程被判为字面量。流结束时应放宽围栏保护把
    # 正文写入文件，而不是让整章正文连标记一起变成聊天消息、文件留空。
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    results = [
        proc.process_content("```markdown\n<file>"),
        proc.process_content("第一段正文。"),
        proc.process_content("</file>\n```"),
    ]
    final = proc.finalize_on_stream_end()
    assert final.file_complete is True
    assert final.final_content == "第一段正文。"
    convo = _all_conversation([*results, final])
    assert "第一段正文。" not in convo
    assert "<file>" not in convo
    assert proc.state == StreamState.IDLE


def test_fenced_format_explanation_without_end_marker_stays_conversation():
    # 只在围栏里解释格式、没有配对的 </file>：不是文件正文，流结束时仍按叙述
    # flush 进对话，文件保持未写入（交由工作流的空文件纠正循环重跑 writer）。
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    narration = "格式示例：\n```\n<file>\n```\n请确认后我再写。"
    proc.process_content(narration)
    final = proc.finalize_on_stream_end()
    assert final.file_complete is False
    assert final.conversation_content == narration
    assert proc.state == StreamState.IDLE


def test_at_eof_rescan_still_honours_control_marker_guard():
    # at_eof 复扫命中开始标记后走的是 WRITING finalize 路径，因此仍受 control
    # marker 污染守卫约束：交接叙述不得被当成正文落库。
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    proc.process_content("输出格式```\n")
    proc.process_content("<file>正文文件已创建。\n\n")
    proc.process_content("### 已交接给 writer。[TASK_COMPLETE]")
    final = proc.finalize_on_stream_end()
    assert final.file_complete is False
    assert final.conversation_content == (
        "输出格式```\n正文文件已创建。\n\n### 已交接给 writer。[TASK_COMPLETE]"
    )
    assert proc.state == StreamState.IDLE


def test_inline_code_narration_stays_conversation_at_stream_end():
    # 行内代码里的 `<file>` 到流结束仍是字面量，不能被 at_eof 复扫误判成
    # 真实开始标记而把叙述写进文件。
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    narration = "我会用 `<file>` 标记开始输出，请稍等。"
    proc.process_content(narration)
    final = proc.finalize_on_stream_end()
    assert final.file_complete is False
    assert final.conversation_content == narration
    assert proc.state == StreamState.IDLE


def test_end_marker_split_across_chunks_still_completes():
    results, proc = _drive(["<file>你好", "</fi", "le>尾巴"])
    assert proc.state == StreamState.IDLE
    completed = next(r for r in results if r.file_complete)
    assert completed.final_content == "你好"
    assert _all_conversation(results) == "尾巴"


def test_drain_ignores_inline_code_end_marker():
    proc = StreamProcessor()
    proc.start_file_write("file-1")
    proc.process_content("<file>")
    proc.process_content("x" * (BUFFER_MAX_SIZE + 100))
    assert proc.state == StreamState.DRAINING
    leaked = proc.process_content("尾部提到 `</file>` 仍是溢出内容")
    assert leaked.conversation_content == ""
    assert proc.state == StreamState.DRAINING
    closing = proc.process_content("</file>之后的对话")
    assert closing.conversation_content == "之后的对话"
    assert proc.state == StreamState.IDLE
