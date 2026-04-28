import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RouteChangeTracker } from "../RouteChangeTracker";

const { trackPageViewMock } = vi.hoisted(() => ({
  trackPageViewMock: vi.fn(),
}));

vi.mock("../../lib/analytics", () => ({
  trackPageView: trackPageViewMock,
}));

function NavigationHarness() {
  const navigate = useNavigate();

  return (
    <button type="button" onClick={() => navigate("/pricing")}>
      go
    </button>
  );
}

describe("RouteChangeTracker", () => {
  beforeEach(() => {
    trackPageViewMock.mockReset();
  });

  it("tracks initial render and route changes", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <RouteChangeTracker />
        <Routes>
          <Route path="/dashboard" element={<NavigationHarness />} />
          <Route path="/pricing" element={<div>pricing</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(trackPageViewMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "go" }));
    expect(trackPageViewMock).toHaveBeenCalledTimes(2);
  });
});
