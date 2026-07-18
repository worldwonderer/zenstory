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
