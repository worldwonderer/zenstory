import { describe, expect, it } from "vitest";

import {
  applyPendingEditsToDiffs,
  buildPendingEditsFromDiffs,
  buildReviewSegmentsFromDiffs,
  computeParagraphReviewDiffs,
} from "../diffReview";

describe("diffReview paragraph helpers", () => {
  it("turns a paragraph rewrite into a single replace edit", () => {
    const original = [
      "第一段保持不变。",
      "",
      "第二段原文。",
      "",
      "第三段保持不变。",
    ].join("\n");
    const modified = [
      "第一段保持不变。",
      "",
      "第二段改写后内容。",
      "",
      "第三段保持不变。",
    ].join("\n");

    const diffs = computeParagraphReviewDiffs(original, modified);
    const edits = buildPendingEditsFromDiffs(diffs);

    expect(edits).toHaveLength(1);
    expect(edits[0]).toMatchObject({
      id: "edit-0",
      op: "replace",
      oldText: "第二段原文。\n\n",
      newText: "第二段改写后内容。\n\n",
      status: "pending",
    });
    expect(applyPendingEditsToDiffs(diffs, edits)).toBe(modified);
  });

  it("keeps the original content when an inserted paragraph is rejected", () => {
    const original = ["开头段落。", "", "结尾段落。"].join("\n");
    const modified = ["开头段落。", "", "新增段落。", "", "结尾段落。"].join("\n");

    const diffs = computeParagraphReviewDiffs(original, modified);
    const edits = buildPendingEditsFromDiffs(diffs);

    expect(edits).toHaveLength(1);
    expect(edits[0]).toMatchObject({
      id: "edit-0",
      op: "insert_after",
      oldText: "",
      newText: "新增段落。\n\n",
      status: "pending",
    });

    const rejectedEdits = edits.map((edit) => ({ ...edit, status: "rejected" as const }));

    expect(applyPendingEditsToDiffs(diffs, rejectedEdits)).toBe(original);
  });

  it("preserves stable edit indexes for replace + insert sequences", () => {
    const original = ["保留段落。", "", "旧段落。"].join("\n");
    const modified = ["保留段落。", "", "新段落。", "", "补充段落。"].join("\n");

    const segments = buildReviewSegmentsFromDiffs(
      computeParagraphReviewDiffs(original, modified)
    );

    expect(segments).toEqual([
      { type: "equal", text: "保留段落。\n\n" },
      {
        type: "replace",
        text: "旧段落。",
        newText: "新段落。\n\n",
        editIndex: 0,
      },
      {
        type: "insert",
        text: "补充段落。",
        editIndex: 1,
      },
    ]);
  });

  it("filters unchanged replacements created by whitespace-only differences", () => {
    const original = ["“这是我们的合作方案。”", "", "第二段原文。"].join("\n");
    const modified = ["“这是我们的合作方案。”   ", "", "第二段改写。"].join("\n");

    const diffs = computeParagraphReviewDiffs(original, modified);
    const edits = buildPendingEditsFromDiffs(diffs);

    expect(edits).toHaveLength(1);
    expect(edits[0]).toMatchObject({
      id: "edit-0",
      op: "replace",
      oldText: "第二段原文。",
      newText: "第二段改写。",
      status: "pending",
    });
  });
});
