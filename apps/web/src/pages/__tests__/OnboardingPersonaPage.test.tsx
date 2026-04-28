import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();
const mockGetPersonaOnboardingData = vi.fn();
const mockSavePersonaOnboardingData = vi.fn();

let mockUser: { id: string } | null = { id: "user-onboarding-1" };
let mockLocationState: { from?: { pathname?: string; search?: string; hash?: string } } | null = {
  from: { pathname: "/dashboard/projects", search: "", hash: "" },
};

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
      return key;
    },
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}));

vi.mock("../../lib/onboardingPersona", () => ({
  getPersonaOnboardingData: (...args: unknown[]) => mockGetPersonaOnboardingData(...args),
  savePersonaOnboardingData: (...args: unknown[]) => mockSavePersonaOnboardingData(...args),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({
      pathname: "/onboarding/persona",
      search: "",
      hash: "",
      key: "test",
      state: mockLocationState,
    }),
  };
});

import OnboardingPersonaPage from "../OnboardingPersonaPage";

const renderPage = () =>
  render(
    <MemoryRouter>
      <OnboardingPersonaPage />
    </MemoryRouter>
  );

describe("OnboardingPersonaPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = { id: "user-onboarding-1" };
    mockLocationState = { from: { pathname: "/dashboard/projects", search: "", hash: "" } };
    mockGetPersonaOnboardingData.mockReturnValue(null);
    mockSavePersonaOnboardingData.mockReturnValue({
      version: 1,
      completed_at: "2026-03-08T00:00:00.000Z",
      selected_personas: [],
      selected_goals: [],
      experience_level: "beginner",
      skipped: false,
    });
  });

  it("returns empty render when user is missing", () => {
    mockUser = null;
    const { container } = renderPage();

    expect(container).toBeEmptyDOMElement();
  });

  it("restores existing onboarding data and preselects personas", () => {
    mockGetPersonaOnboardingData.mockReturnValue({
      version: 1,
      completed_at: "2026-03-07T09:00:00.000Z",
      selected_personas: ["explorer"],
      selected_goals: ["monetize"],
      experience_level: "advanced",
      skipped: false,
    });

    renderPage();

    expect(screen.getByText("已读取你之前的画像，可随时更新")).toBeInTheDocument();
    expect(screen.getByText(/1\s*\/\s*3 已选/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /explorer/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("enforces max persona selection limit", () => {
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /serial/i }));
    fireEvent.click(screen.getByRole("button", { name: /professional/i }));
    fireEvent.click(screen.getByRole("button", { name: /fanfic/i }));

    expect(screen.getByText("最多可选 3 项。可先取消一个，再继续选择。")).toBeInTheDocument();
    expect(screen.getByText(/3\s*\/\s*3 已选/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /fanfic/i })).toHaveAttribute("aria-pressed", "false");
  });

  it("saves skipped onboarding and redirects to /dashboard when source path is onboarding", async () => {
    mockLocationState = { from: { pathname: "/onboarding/persona" } };

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "暂时跳过" }));

    await waitFor(() => {
      expect(mockSavePersonaOnboardingData).toHaveBeenCalledWith("user-onboarding-1", {
        selected_personas: [],
        selected_goals: [],
        experience_level: "beginner",
        skipped: true,
      });
    });
    expect(mockNavigate).toHaveBeenCalledWith("/dashboard", {
      replace: true,
      state: { startDashboardCoachmark: true },
    });
  });

  it("submits selected personas/goals and navigates to source path", async () => {
    renderPage();

    const submitButton = screen.getByRole("button", { name: "保存并进入工作台" });
    expect(submitButton).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /explorer/i }));
    fireEvent.click(screen.getByRole("button", { name: /monetize/i }));
    fireEvent.click(screen.getByRole("button", { name: /advanced/i }));
    expect(submitButton).toBeEnabled();

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSavePersonaOnboardingData).toHaveBeenCalledWith("user-onboarding-1", {
        selected_personas: ["explorer"],
        selected_goals: ["monetize"],
        experience_level: "advanced",
        skipped: false,
      });
    });
    expect(mockNavigate).toHaveBeenCalledWith("/dashboard/projects", {
      replace: true,
      state: undefined,
    });
  });

  it("preserves source search/hash when navigating back after submit", async () => {
    mockLocationState = {
      from: {
        pathname: "/project/project-1",
        search: "?file=file-2&tab=outline",
        hash: "#section-1",
      },
    };
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /explorer/i }));
    const submitButton = screen.getByRole("button", { name: "保存并进入工作台" });

    await waitFor(() => {
      expect(submitButton).toBeEnabled();
    });

    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        "/project/project-1?file=file-2&tab=outline#section-1",
        { replace: true, state: undefined },
      );
    });
  });
});
