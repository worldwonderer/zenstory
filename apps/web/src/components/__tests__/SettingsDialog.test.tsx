import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockChangeLanguage = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: (ns?: string) => {
    if (ns === "settings") {
      return {
        t: (key: string, fallback?: string) => {
          const map: Record<string, string> = {
            title: "Settings",
            "nav.profile": "Profile",
            "nav.general": "General",
            "nav.subscription": "Subscription",
            "nav.points": "Points",
            "nav.referral": "Referral",
            "language.title": "Language",
            "theme.mode": "Theme",
            "theme.dark": "Dark",
            "theme.light": "Light",
            "theme.color": "Accent Color",
            "profile.anonymous": "Anonymous",
          };
          return map[key] ?? fallback ?? key;
        },
      };
    }

    if (ns === "auth") {
      return {
        t: (key: string) => {
          const map: Record<string, string> = {
            "logout.loading": "Logging out",
            "logout.button": "Logout",
          };
          return map[key] ?? key;
        },
      };
    }

    return {
      t: (key: string) => key,
      i18n: {
        language: "zh-CN",
        resolvedLanguage: "zh-CN",
        changeLanguage: mockChangeLanguage,
      },
    };
  },
}));

vi.mock("@tanstack/react-query", () => ({
  useIsFetching: () => 0,
}));

vi.mock("../../contexts/ThemeContext", () => ({
  useTheme: () => ({
    theme: "dark",
    accentColor: "#4a9eff",
    setTheme: vi.fn(),
    setAccentColor: vi.fn(),
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      email: "user@example.com",
      nickname: "Test User",
      avatar_url: null,
    },
    logout: vi.fn(),
  }),
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useIsMobile: () => false,
}));

vi.mock("../UserMenu", () => ({
  UserAvatar: () => <div data-testid="avatar" />,
}));

vi.mock("../subscription/SubscriptionStatus", () => ({
  SubscriptionStatus: () => <div data-testid="subscription-status" />,
}));

vi.mock("../subscription/QuotaBadge", () => ({
  QuotaBadge: () => <div data-testid="quota-badge" />,
}));

vi.mock("../subscription/RedeemCodeModal", () => ({
  RedeemCodeModal: () => null,
}));

vi.mock("../points/RedeemProModal", () => ({
  RedeemProModal: () => null,
}));

vi.mock("../points/DailyCheckIn", () => ({
  DailyCheckIn: () => <div data-testid="daily-checkin" />,
}));

vi.mock("../points/PointsBalance", () => ({
  PointsBalance: () => <div data-testid="points-balance" />,
}));

vi.mock("../points/PointsHistory", () => ({
  PointsHistory: () => <div data-testid="points-history" />,
}));

vi.mock("../points/EarnOpportunities", () => ({
  EarnOpportunities: () => <div data-testid="earn-opportunities" />,
}));

vi.mock("../referral/ReferralStats", () => ({
  ReferralStats: () => <div data-testid="referral-stats" />,
}));

vi.mock("../referral/InviteCodeList", () => ({
  InviteCodeList: () => <div data-testid="invite-code-list" />,
}));

import { SettingsDialog } from "../SettingsDialog";

describe("SettingsDialog language switching", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("highlights zh button for zh-CN locale and persists language switch", () => {
    render(<SettingsDialog isOpen onClose={vi.fn()} />);

    fireEvent.click(screen.getByTestId("settings-tab-general"));

    const zhButton = screen.getByTestId("language-button-zh");
    const enButton = screen.getByTestId("language-button-en");

    expect(zhButton.className).toContain("accent-primary");

    fireEvent.click(enButton);

    expect(mockChangeLanguage).toHaveBeenCalledWith("en");
    expect(localStorage.getItem("zenstory-language")).toBe("en");
  });
});
