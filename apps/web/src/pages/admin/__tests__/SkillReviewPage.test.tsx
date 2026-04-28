import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SkillReviewPage from "../SkillReviewPage";
import { adminApi } from "../../../lib/adminApi";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../../../lib/adminApi", () => ({
  adminApi: {
    getPendingSkills: vi.fn(),
    approveSkill: vi.fn(),
    rejectSkill: vi.fn(),
  },
}));

describe("SkillReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state while pending skills are being loaded", () => {
    (adminApi.getPendingSkills as Mock).mockReturnValue(new Promise(() => {}));

    render(<SkillReviewPage />);
    expect(screen.getByText("common:loading")).toBeInTheDocument();
  });

  it("shows empty state when no pending skills exist", async () => {
    (adminApi.getPendingSkills as Mock).mockResolvedValue([]);

    render(<SkillReviewPage />);

    await waitFor(() => {
      expect(screen.getByText("admin:skills.noPending")).toBeInTheDocument();
    });
  });

  it("shows blocking error when initial load fails", async () => {
    (adminApi.getPendingSkills as Mock).mockRejectedValue(new Error("load pending skills failed"));

    render(<SkillReviewPage />);

    await waitFor(() => {
      expect(screen.getByText("load pending skills failed")).toBeInTheDocument();
    });
  });
});
