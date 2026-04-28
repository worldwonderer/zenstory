import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  mockNavigate,
  mockLogin,
  mockGoogleLogin,
  mockAppleLogin,
  mockGetAllProjects,
} = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockLogin: vi.fn(),
  mockGoogleLogin: vi.fn(),
  mockAppleLogin: vi.fn(),
  mockGetAllProjects: vi.fn(),
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
      if (options && Object.keys(options).length > 0) {
        return `${key}:${JSON.stringify(options)}`;
      }
      return key;
    },
  }),
}));

vi.mock("../../contexts/AuthContext", () => ({
  useAuth: () => ({
    login: mockLogin,
    googleLogin: mockGoogleLogin,
    appleLogin: mockAppleLogin,
    user: null,
    loading: false,
  }),
}));

vi.mock("../../lib/api", () => ({
  projectApi: {
    getAll: mockGetAllProjects,
  },
}));

vi.mock("../../config/auth", () => ({
  authConfig: {
    registrationEnabled: true,
    forgotPasswordEnabled: true,
    oauthProviders: {
      google: { enabled: false },
      apple: { enabled: false },
    },
  },
  hasOAuthProviders: () => false,
}));

vi.mock("../../components/PublicHeader", () => ({
  PublicHeader: () => <div data-testid="public-header" />,
}));

vi.mock("../../components/LoadingSpinner", () => ({
  LoadingSpinner: () => <div data-testid="loading-spinner" />,
}));

vi.mock("../../components/Logo", () => ({
  LogoMark: () => <div data-testid="logo-mark" />,
}));

import Login from "../Login";

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAllProjects.mockResolvedValue([]);
  });

  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Login />
      </MemoryRouter>
    );

  it("disables submit until identifier and password are both provided", async () => {
    renderPage();

    const submitButton = screen.getByTestId("login-submit");
    expect(submitButton).toBeDisabled();

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "writer@example.com" },
    });
    expect(submitButton).toBeDisabled();

    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "SecurePass123!" },
    });
    expect(submitButton).toBeEnabled();
  });

  it("does not render redundant inline helper text for login method", () => {
    renderPage();
    expect(screen.queryByText(/auth:login.helper/)).not.toBeInTheDocument();
  });

  it("shows loading spinner and busy state while login request is pending", async () => {
    mockLogin.mockReturnValue(new Promise<void>(() => {}));
    const user = userEvent.setup();
    renderPage();

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "writer@example.com" },
    });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "SecurePass123!" },
    });

    const submitButton = screen.getByTestId("login-submit");
    await user.click(submitButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("writer@example.com", "SecurePass123!");
    });

    expect(submitButton).toBeDisabled();
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
    expect(screen.getByTestId("login-form")).toHaveAttribute("aria-busy", "true");
  });

  it("trims identifier and navigates to dashboard after successful login", async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue(undefined);
    renderPage();

    fireEvent.change(screen.getByTestId("email-input"), {
      target: { value: "  writer@example.com  " },
    });
    fireEvent.change(screen.getByTestId("password-input"), {
      target: { value: "SecurePass123!" },
    });

    await user.click(screen.getByTestId("login-submit"));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("writer@example.com", "SecurePass123!");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });
});
