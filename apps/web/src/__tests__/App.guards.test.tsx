import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  auth: {
    user: null as { id: string; email_verified?: boolean; email?: string } | null,
    loading: false,
  },
  requireOnboarding: false,
  shouldRequireCalls: [] as unknown[],
  initialPath: "/",
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    BrowserRouter: ({ children }: { children: ReactNode }) => (
      <actual.MemoryRouter initialEntries={[state.initialPath]}>{children}</actual.MemoryRouter>
    ),
  };
});

vi.mock("react-helmet-async", () => ({
  HelmetProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../components/Toast", () => ({
  ToastContainer: () => <div data-testid="toast-container" />,
}));

vi.mock("../components/PageLoader", () => ({
  PageLoader: () => <div>Page Loader</div>,
}));

vi.mock("../components/Layout", () => ({
  Layout: () => <div>Layout</div>,
}));

vi.mock("../components/sidebar/Sidebar", () => ({
  Sidebar: () => <div>Sidebar</div>,
}));

vi.mock("../components/Editor", () => ({
  Editor: () => <div>Editor</div>,
}));

vi.mock("../components/ChatPanel", () => ({
  ChatPanel: () => <div>Chat Panel</div>,
}));

vi.mock("../components/Helmet", () => ({
  SEOHelmet: () => null,
}));

vi.mock("../providers/SEOProvider", () => ({
  SEOProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../providers/CommonProviders", () => ({
  CommonProviders: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../providers/ProtectedProviders", () => ({
  ProtectedProviders: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../contexts/ThemeContext", () => ({
  ThemeProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../contexts/FileSearchContext", () => ({
  FileSearchProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../contexts/AuthContext", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useAuth: () => state.auth,
}));

vi.mock("../contexts/ProjectContext", () => ({
  useProject: () => ({
    setCurrentProjectId: vi.fn(),
    currentProject: null,
    loading: false,
    error: null,
    refreshProjects: vi.fn(),
    projects: [],
    setSelectedItem: vi.fn(),
  }),
}));

vi.mock("../lib/onboardingPersona", () => ({
  shouldRequirePersonaOnboarding: (user: unknown) => {
    state.shouldRequireCalls.push(user);
    return state.requireOnboarding;
  },
}));

vi.mock("../lib/authFlow", () => ({
  normalizePlanIntent: () => null,
}));

vi.mock("../lib/logger", () => ({
  logger: {
    log: vi.fn(),
    warn: vi.fn(),
  },
}));

vi.mock("../lib/api", () => ({
  fileApi: {
    get: vi.fn(),
  },
}));

vi.mock("../pages/HomePage", () => ({
  default: () => <div>Home Page</div>,
}));

vi.mock("../pages/Login", () => ({
  default: () => <div>Login Page</div>,
}));

vi.mock("../pages/Register", () => ({
  default: () => <div>Register Page</div>,
}));

vi.mock("../pages/ForgotPassword", () => ({
  default: () => <div>Forgot Password Page</div>,
}));

vi.mock("../pages/Dashboard", () => ({
  default: () => <div>Dashboard Page</div>,
}));

vi.mock("../pages/DashboardHome", () => ({
  default: () => <div>Dashboard Home</div>,
}));

vi.mock("../pages/OnboardingPersonaPage", () => ({
  default: () => <div>Onboarding Persona Page</div>,
}));

vi.mock("../pages/VerifyEmail", () => ({
  default: () => <div>Verify Email Page</div>,
}));

vi.mock("../components/AdminRoute", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("../components/admin/AdminLayout", () => ({
  default: () => <div>Admin Layout</div>,
}));

vi.mock("../pages/admin/AdminDashboard", () => ({
  default: () => <div>Admin Dashboard</div>,
}));

import App from "../App";

const renderAppAt = (path: string) => {
  state.initialPath = path;
  return render(<App />);
};

describe("App route guards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    state.auth.user = null;
    state.auth.loading = false;
    state.requireOnboarding = false;
    state.shouldRequireCalls = [];
    state.initialPath = "/";
  });

  it("redirects unauthenticated users from protected routes to login", async () => {
    renderAppAt("/dashboard");

    await waitFor(() => {
      expect(screen.getByText("Login Page")).toBeInTheDocument();
    });
  });

  it("redirects authenticated users away from login to dashboard", async () => {
    state.auth.user = { id: "user-auth" };

    renderAppAt("/login");

    await waitFor(() => {
      expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    });
  });

  it("shows loading indicator while auth guard is resolving", () => {
    state.auth.loading = true;

    renderAppAt("/dashboard");

    expect(screen.getByText("Page Loader")).toBeInTheDocument();
  });

  it("redirects authenticated users to onboarding when required", async () => {
    state.auth.user = { id: "user-1" };
    state.requireOnboarding = true;

    renderAppAt("/dashboard");

    await waitFor(() => {
      expect(screen.getByText("Onboarding Persona Page")).toBeInTheDocument();
    });
    expect(state.shouldRequireCalls).toEqual([{ id: "user-1" }]);
  });

  it("does not loop-redirect when already on onboarding route", async () => {
    state.auth.user = { id: "user-2" };
    state.requireOnboarding = true;

    renderAppAt("/onboarding/persona");

    await waitFor(() => {
      expect(screen.getByText("Onboarding Persona Page")).toBeInTheDocument();
    });
    expect(state.shouldRequireCalls).toEqual([]);
  });

  it("skips onboarding redirects on admin routes", async () => {
    state.auth.user = { id: "admin-user" };
    state.requireOnboarding = true;

    renderAppAt("/admin");

    await waitFor(() => {
      expect(screen.getByText("Admin Layout")).toBeInTheDocument();
    });
    expect(state.shouldRequireCalls).toEqual([]);
  });

  it("allows authenticated users through when onboarding is not required", async () => {
    state.auth.user = { id: "user-3" };
    state.requireOnboarding = false;

    renderAppAt("/dashboard");

    await waitFor(() => {
      expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
    });
    expect(state.shouldRequireCalls.length).toBeGreaterThan(0);
    expect(state.shouldRequireCalls).toContainEqual({ id: "user-3" });
  });
});
