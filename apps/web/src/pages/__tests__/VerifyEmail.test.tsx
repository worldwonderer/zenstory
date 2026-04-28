import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockNavigate, mockVerifyEmail, mockResendVerification, mockCheckVerification } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockVerifyEmail: vi.fn(),
  mockResendVerification: vi.fn(),
  mockCheckVerification: vi.fn(),
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
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === "auth:verifyEmail.subtitle" && options?.email) {
        return `verify-email:${String(options.email)}`;
      }
      return key;
    },
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    verifyEmail: mockVerifyEmail,
    resendVerification: mockResendVerification,
  }),
}));

vi.mock("../../lib/api", () => ({
  authApi: {
    checkVerification: mockCheckVerification,
  },
}));

vi.mock("../../components/PublicHeader", () => ({
  PublicHeader: () => <div data-testid="public-header" />,
}));

import VerifyEmail from "../VerifyEmail";

describe("VerifyEmail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCheckVerification.mockResolvedValue({
      email_verified: false,
      resend_cooldown_seconds: 60,
      verification_code_ttl_seconds: 300,
    });
  });

  const renderPage = (email: string, planIntent?: "free" | "pro" | null) =>
    render(
      <MemoryRouter>
        <VerifyEmail email={email} planIntent={planIntent} />
      </MemoryRouter>
    );

  it("shows guard UI when email is missing", async () => {
    renderPage("");

    await waitFor(() => {
      expect(screen.getByText("auth:errors.missingVerificationEmail")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "auth:verifyEmail.goToRegister" })).toBeInTheDocument();
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(mockVerifyEmail).not.toHaveBeenCalled();
    expect(mockResendVerification).not.toHaveBeenCalled();
  });

  it("keeps paid plan query when navigating from missing-email guard actions", async () => {
    renderPage("", "pro");

    await waitFor(() => {
      expect(screen.getByText("auth:errors.missingVerificationEmail")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.goToRegister" }));
    expect(mockNavigate).toHaveBeenCalledWith("/register?plan=pro");

    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.backToLogin" }));
    expect(mockNavigate).toHaveBeenCalledWith("/login?plan=pro");
  });

  it("keeps paid plan query when navigating back to login in normal state", async () => {
    renderPage("user@example.com", "pro");

    await waitFor(() => {
      expect(mockCheckVerification).toHaveBeenCalledWith("user@example.com");
    });

    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.backToLogin" }));
    expect(mockNavigate).toHaveBeenCalledWith("/login?plan=pro");
  });

  it("keeps plan intent when navigating from missing-email guard actions", async () => {
    renderPage("", "pro");

    await waitFor(() => {
      expect(screen.getByText("auth:errors.missingVerificationEmail")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.goToRegister" }));
    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.backToLogin" }));

    expect(mockNavigate).toHaveBeenNthCalledWith(1, "/register?plan=pro");
    expect(mockNavigate).toHaveBeenNthCalledWith(2, "/login?plan=pro");
  });

  it("keeps plan intent when navigating back to login in normal state", async () => {
    renderPage("user@example.com", "pro");

    await waitFor(() => {
      expect(mockCheckVerification).toHaveBeenCalledWith("user@example.com");
    });

    fireEvent.click(screen.getByRole("button", { name: "auth:verifyEmail.backToLogin" }));
    expect(mockNavigate).toHaveBeenCalledWith("/login?plan=pro");
  });

  it("redirects to billing for paid plan intent after successful verification", async () => {
    mockVerifyEmail.mockResolvedValue(undefined);
    renderPage("user@example.com", "pro");

    const inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(6);

    fireEvent.change(inputs[0], { target: { value: "1" } });
    fireEvent.change(inputs[1], { target: { value: "2" } });
    fireEvent.change(inputs[2], { target: { value: "3" } });
    fireEvent.change(inputs[3], { target: { value: "4" } });
    fireEvent.change(inputs[4], { target: { value: "5" } });
    fireEvent.change(inputs[5], { target: { value: "6" } });

    await waitFor(() => {
      expect(mockVerifyEmail).toHaveBeenCalledWith("user@example.com", "123456");
    });

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard/billing?plan=pro");
    }, { timeout: 3000 });
  });

  it("allows resend when server reports ttl expired and cooldown finished", async () => {
    mockCheckVerification.mockResolvedValue({
      email_verified: false,
      resend_cooldown_seconds: 0,
      verification_code_ttl_seconds: 0,
    });

    renderPage("user@example.com");

    await waitFor(() => {
      expect(mockCheckVerification).toHaveBeenCalledWith("user@example.com");
    });

    const resendButton = await screen.findByRole("button", {
      name: "auth:verifyEmail.resendButton",
    });
    expect(resendButton).toBeEnabled();
  });

  it("refreshes countdown from server after resend succeeds", async () => {
    mockCheckVerification
      .mockResolvedValueOnce({
        email_verified: false,
        resend_cooldown_seconds: 0,
        verification_code_ttl_seconds: 0,
      })
      .mockResolvedValueOnce({
        email_verified: false,
        resend_cooldown_seconds: 45,
        verification_code_ttl_seconds: 300,
      });
    mockResendVerification.mockResolvedValue(undefined);

    renderPage("user@example.com");

    const resendButton = await screen.findByRole("button", {
      name: "auth:verifyEmail.resendButton",
    });
    expect(resendButton).toBeEnabled();

    fireEvent.click(resendButton);

    await waitFor(() => {
      expect(mockResendVerification).toHaveBeenCalledWith("user@example.com");
    });
    await waitFor(() => {
      expect(mockCheckVerification).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.getByRole("button", { name: "auth:verifyEmail.resendButtonWithCount" })
    ).toBeDisabled();
  });
});
