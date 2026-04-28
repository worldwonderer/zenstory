import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DiffReviewEditPreview } from "../DiffReviewEditPreview";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe("DiffReviewEditPreview", () => {
  it("shows both old + new text for replace operations", () => {
    render(
      <DiffReviewEditPreview
        edit={{
          id: "edit-1",
          op: "replace",
          oldText: "OLD_TEXT",
          newText: "NEW_TEXT",
          status: "pending",
        }}
      />
    );

    expect(screen.getByText("OLD_TEXT")).toBeInTheDocument();
    expect(screen.getByText("NEW_TEXT")).toBeInTheDocument();
  });

  it("renders bounded scroll areas for long review text", () => {
    const { container } = render(
      <DiffReviewEditPreview
        edit={{
          id: "edit-2",
          op: "replace",
          oldText: "LONG_OLD_TEXT",
          newText: "LONG_NEW_TEXT",
          status: "pending",
        }}
      />
    );

    expect(container.querySelectorAll(".overflow-y-auto")).toHaveLength(2);
  });
});
