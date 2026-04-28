import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockNavigate, mockLanguage, mockAuthConfig } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockLanguage: { value: "en-US" },
  mockAuthConfig: {
    registrationEnabled: true,
  },
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: {
      language: mockLanguage.value,
      resolvedLanguage: mockLanguage.value,
    },
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: null,
  }),
}));

vi.mock("../../hooks/usePreloadRoute", () => ({
  usePreloadRoute: () => vi.fn(),
}));

vi.mock("../../config/auth", () => ({
  authConfig: mockAuthConfig,
}));

vi.mock("../../components/PublicHeader", () => ({
  PublicHeader: () => <div data-testid="public-header" />,
}));

import HomePage from "../HomePage";

const setupMatchMedia = (reducedMotion: boolean) => {
  return vi.spyOn(window, "matchMedia").mockImplementation((query: string) => ({
    matches: query === "(prefers-reduced-motion: reduce)" ? reducedMotion : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
};

describe("HomePage reduced-motion carousel behavior", () => {
  let mockedNow = 0;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockLanguage.value = "en-US";
    mockAuthConfig.registrationEnabled = true;
    mockedNow = 0;
    vi.spyOn(Date, "now").mockImplementation(() => mockedNow);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("does not auto-rotate scenes when reduced-motion is enabled", () => {
    setupMatchMedia(true);

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    const createButton = screen.getByRole("button", { name: "home:demo.scenes.create" });
    const suggestButton = screen.getByRole("button", { name: "home:demo.scenes.suggest" });

    expect(createButton.className).toContain("text-white");
    expect(suggestButton.className).not.toContain("text-white");
    expect(container.querySelector('div[style*="width"]')).toBeNull();

    act(() => {
      mockedNow = 20000;
      vi.advanceTimersByTime(20000);
    });

    expect(createButton.className).toContain("text-white");
    expect(suggestButton.className).not.toContain("text-white");
  });

  it("auto-rotates to the next scene when reduced-motion is disabled", () => {
    setupMatchMedia(false);

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    const createButton = screen.getByRole("button", { name: "home:demo.scenes.create" });
    const suggestButton = screen.getByRole("button", { name: "home:demo.scenes.suggest" });

    expect(createButton.className).toContain("text-white");
    expect(suggestButton.className).not.toContain("text-white");
    expect(container.querySelector('div[style*="width"]')).not.toBeNull();

    act(() => {
      mockedNow = 5600;
      vi.advanceTimersByTime(5600);
    });

    expect(createButton.className).not.toContain("text-white");
    expect(suggestButton.className).toContain("text-white");
  });

  it("renders social proof metrics in an i18n-friendly English format", () => {
    setupMatchMedia(true);
    mockLanguage.value = "en-US";

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    const creators = `${new Intl.NumberFormat("en-US").format(2000)}+`;
    const words = `${new Intl.NumberFormat("en-US", {
      notation: "compact",
      compactDisplay: "short",
      maximumFractionDigits: 1,
    }).format(12000000)}+`;
    const rating = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(4.9);

    expect(screen.getByText(creators)).toBeInTheDocument();
    expect(screen.getByText(words)).toBeInTheDocument();
    expect(screen.getByText(rating)).toBeInTheDocument();
    expect(screen.queryByText("1,200万+")).not.toBeInTheDocument();
  });

  it("renders social proof metrics in an i18n-friendly Chinese format", () => {
    setupMatchMedia(true);
    mockLanguage.value = "zh-CN";

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    const creators = `${new Intl.NumberFormat("zh-CN").format(2000)}+`;
    const words = `${new Intl.NumberFormat("zh-CN", {
      notation: "compact",
      compactDisplay: "short",
      maximumFractionDigits: 1,
    }).format(12000000)}+`;
    const rating = new Intl.NumberFormat("zh-CN", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(4.9);

    expect(screen.getByText(creators)).toBeInTheDocument();
    expect(screen.getByText(words)).toBeInTheDocument();
    expect(screen.getByText(rating)).toBeInTheDocument();
  });

  it("adds source attribution and preserves plan for core homepage CTA entries", () => {
    setupMatchMedia(true);

    render(
      <MemoryRouter initialEntries={["/?plan=pro"]}>
        <HomePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("link", { name: "home:pricingTeaser.viewPricing" })).toHaveAttribute(
      "href",
      "/pricing?plan=pro&source=home_pricing_teaser"
    );

    fireEvent.click(screen.getByRole("button", { name: "home:hero.cta" }));
    expect(mockNavigate).toHaveBeenLastCalledWith("/register?plan=pro&source=home_hero");

    fireEvent.click(screen.getByRole("button", { name: "home:pricingTeaser.primaryCta" }));
    expect(mockNavigate).toHaveBeenLastCalledWith("/register?plan=pro&source=home_pricing_teaser");

    fireEvent.click(screen.getByRole("button", { name: "home:cta.button" }));
    expect(mockNavigate).toHaveBeenLastCalledWith("/register?plan=pro&source=home_cta");
  });

  it("adds source attribution for project type card entry", () => {
    setupMatchMedia(true);

    render(
      <MemoryRouter initialEntries={["/?plan=pro"]}>
        <HomePage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: /home:projectTypes\.novel\.name/ }));
    expect(mockNavigate).toHaveBeenCalledWith("/register?plan=pro&source=home_project_type_card");
  });

  it("renders project type cards as keyboard-focusable buttons", () => {
    setupMatchMedia(true);

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    const novelCard = screen.getByRole("button", { name: /home:projectTypes\.novel\.name/ });
    expect(novelCard.className).toContain("focus-visible:ring-2");
  });

  it("falls back to login entry while keeping source attribution when registration is disabled", () => {
    setupMatchMedia(true);
    mockAuthConfig.registrationEnabled = false;

    render(
      <MemoryRouter initialEntries={["/?plan=pro"]}>
        <HomePage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "home:hero.cta" }));
    expect(mockNavigate).toHaveBeenCalledWith("/login?plan=pro&source=home_hero");

    fireEvent.click(screen.getByRole("button", { name: /home:projectTypes\.novel\.name/ }));
    expect(mockNavigate).toHaveBeenCalledWith("/login?plan=pro&source=home_project_type_card");
  });
});
