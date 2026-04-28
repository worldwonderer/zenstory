import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MaterialsPage from "../MaterialsPage";
import { ApiError } from "../../lib/apiClient";
import { MATERIALS_UPLOAD_MAX_CHARACTERS } from "../../lib/materialUploadValidation";

const mockNavigate = vi.fn();
const mockList = vi.fn();
const mockUpload = vi.fn();
const mockDelete = vi.fn();
const mockRetry = vi.fn();
const mockGetStatus = vi.fn();
const mockGetQuota = vi.fn();
const trackEventMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?: string | Record<string, unknown>,
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof defaultValueOrOptions === "string") {
        if (!maybeOptions) return defaultValueOrOptions;
        let output = defaultValueOrOptions;
        for (const [optionKey, optionValue] of Object.entries(maybeOptions)) {
          output = output.replace(`{{${optionKey}}}`, String(optionValue));
        }
        return output;
      }
      if (
        defaultValueOrOptions &&
        typeof defaultValueOrOptions === "object" &&
        "defaultValue" in defaultValueOrOptions
      ) {
        const defaultValue = defaultValueOrOptions.defaultValue;
        if (typeof defaultValue === "string") {
          let output = defaultValue;
          for (const [optionKey, optionValue] of Object.entries(defaultValueOrOptions)) {
            if (optionKey === "defaultValue") continue;
            output = output.replace(`{{${optionKey}}}`, String(optionValue));
          }
          return output;
        }
      }
      return key;
    },
    i18n: { language: "zh-CN" },
  }),
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useIsMobile: () => false,
  useIsTablet: () => false,
}));

vi.mock("../../lib/materialsApi", () => ({
  materialsApi: {
    list: () => mockList(),
    upload: (...args: unknown[]) => mockUpload(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    retry: (...args: unknown[]) => mockRetry(...args),
  },
}));

vi.mock("../../lib/subscriptionApi", () => ({
  subscriptionApi: {
    getStatus: () => mockGetStatus(),
    getQuota: () => mockGetQuota(),
  },
  subscriptionQueryKeys: {
    status: () => ["subscription-status", "test-user"],
    quota: () => ["subscription-quota", "test-user"],
  },
}));

vi.mock("../../lib/analytics", () => ({
  trackEvent: (...args: unknown[]) => trackEventMock(...args),
}));

vi.mock("../../config/materials", () => ({
  materialsConfig: {
    relationshipsEnabled: false,
  },
}));

vi.mock("../../components/subscription/UpgradePromptModal", () => ({
  UpgradePromptModal: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="upgrade-modal">{title}</div> : null,
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe("MaterialsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue([]);
    mockUpload.mockResolvedValue({
      novel_id: 1,
      title: "test",
      job_id: "job-1",
      status: "pending",
      message: "ok",
    });
    mockDelete.mockResolvedValue(undefined);
    mockRetry.mockResolvedValue({ message: "retry queued" });
    mockGetStatus.mockResolvedValue({
      tier: "pro",
      status: "active",
      display_name: "Pro",
      days_remaining: 30,
      current_period_end: null,
      features: {
        materials_library_access: true,
      },
    });
    mockGetQuota.mockResolvedValue({
      ai_conversations: { used: 0, limit: -1, reset_at: null },
      projects: { used: 0, limit: -1, reset_at: null },
      material_uploads: { used: 0, limit: 5, reset_at: null },
      material_decompositions: { used: 0, limit: 5, reset_at: null },
      skill_creates: { used: 0, limit: 20, reset_at: null },
      inspiration_copies: { used: 0, limit: 10, reset_at: null },
    });
  });

  it("renders teaser state for free users and skips workspace queries", async () => {
    mockGetStatus.mockResolvedValueOnce({
      tier: "free",
      status: "none",
      display_name: "免费版",
      days_remaining: null,
      current_period_end: null,
      features: {
        materials_library_access: false,
      },
    });

    render(<MaterialsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText("上传参考小说，一键拆出角色、剧情线和世界观")
      ).toBeInTheDocument();
    });

    expect(mockList).not.toHaveBeenCalled();
    expect(trackEventMock).toHaveBeenCalledWith(
      "materials_teaser_exposed",
      expect.objectContaining({ source: "materials_teaser" }),
    );

    const teaserSecondaryButton = screen.getByRole("button", {
      name: "查看权益详情",
    });
    expect(teaserSecondaryButton.className).toContain("text-[hsl(var(--accent-primary))]");
    expect(teaserSecondaryButton.className).not.toContain("btn-secondary");
  });

  it("shows exhausted state for paid users without upgrade modal", async () => {
    mockList.mockResolvedValueOnce([
      {
        id: "novel-1",
        title: "Broken Novel",
        original_filename: "broken.txt",
        status: "failed",
        chapters_count: 0,
        error_message: "failed once",
      },
    ]);
    mockGetQuota.mockResolvedValueOnce({
      ai_conversations: { used: 0, limit: -1, reset_at: null },
      projects: { used: 0, limit: -1, reset_at: null },
      material_uploads: { used: 0, limit: 5, reset_at: null },
      material_decompositions: {
        used: 5,
        limit: 5,
        reset_at: "2026-05-01T00:00:00Z",
      },
      skill_creates: { used: 0, limit: 20, reset_at: null },
      inspiration_copies: { used: 0, limit: 10, reset_at: null },
    });

    render(<MaterialsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText("本月 5 次素材拆解已用完，将于 2026/05/01 自动恢复。")
      ).toBeInTheDocument();
    });

    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
    expect(screen.queryByTestId("upgrade-modal")).not.toBeInTheDocument();
  });

  it("shows error state when subscription status fails instead of teaser", async () => {
    mockGetStatus.mockRejectedValueOnce(new Error("subscription failed"));

    render(<MaterialsPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText("订阅权益状态加载失败，请重试后再查看素材库。")
      ).toBeInTheDocument();
    });

    expect(
      screen.queryByText("上传参考小说，一键拆出角色、剧情线和世界观")
    ).not.toBeInTheDocument();
    expect(trackEventMock).not.toHaveBeenCalledWith(
      "materials_teaser_exposed",
      expect.anything(),
    );
  });

  it("supports keyboard navigation for opening material detail cards", async () => {
    mockList.mockResolvedValueOnce([
      {
        id: "novel-2",
        title: "Keyboard Novel",
        original_filename: "keyboard.txt",
        status: "completed",
        chapters_count: 12,
        error_message: null,
      },
    ]);

    render(<MaterialsPage />, { wrapper: createWrapper() });

    const detailEntry = await screen.findByRole("button", {
      name: /Keyboard Novel/,
    });

    fireEvent.keyDown(detailEntry, { key: "Enter" });
    fireEvent.keyDown(detailEntry, { key: " " });

    expect(mockNavigate).toHaveBeenNthCalledWith(1, "/materials/novel-2");
    expect(mockNavigate).toHaveBeenNthCalledWith(2, "/materials/novel-2");
  });

  it("shows an inline error before upload when the selected file exceeds 300k characters", async () => {
    render(<MaterialsPage />, { wrapper: createWrapper() });

    const openUploadButton = await screen.findByRole("button", {
      name: "materials:upload",
    });
    fireEvent.click(openUploadButton);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    fireEvent.change(fileInput, {
      target: {
        files: [
          new File(
            ["字".repeat(MATERIALS_UPLOAD_MAX_CHARACTERS + 1)],
            "too-long.txt",
            { type: "text/plain" },
          ),
        ],
      },
    });

    await waitFor(() => {
      expect(
        screen.getByText("materials:uploadModal.errors.tooManyCharacters")
      ).toBeInTheDocument();
    });

    expect(mockUpload).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "materials:uploadModal.upload" })
    ).toBeDisabled();
  });

  it("shows materials-specific copy when backend rejects the upload as over-limit", async () => {
    mockUpload.mockRejectedValueOnce(new ApiError(400, "ERR_FILE_CONTENT_TOO_LONG"));

    render(<MaterialsPage />, { wrapper: createWrapper() });

    const openUploadButton = await screen.findByRole("button", {
      name: "materials:upload",
    });
    fireEvent.click(openUploadButton);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(fileInput, {
      target: {
        files: [new File(["valid content"], "valid.txt", { type: "text/plain" })],
      },
    });

    await waitFor(() => {
      expect(screen.getByText("valid.txt")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: "materials:uploadModal.upload" })
    );

    await waitFor(() => {
      expect(
        screen.getByText("materials:uploadModal.errors.tooManyCharacters")
      ).toBeInTheDocument();
    });
  });
});
