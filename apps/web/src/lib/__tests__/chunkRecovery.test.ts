import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  installChunkRecoveryHandlers,
  isChunkLoadError,
  lazyRoute,
  reloadForChunkErrorOnce,
} from "../chunkRecovery";
import { Suspense, createElement } from "react";
import { render, screen } from "@testing-library/react";

describe("chunkRecovery", () => {
  const reloadSpy = vi.fn();
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        ...originalLocation,
        reload: reloadSpy,
      },
    });
  });

  it("detects stale dynamic import failures", () => {
    expect(isChunkLoadError(new Error("Failed to fetch dynamically imported module"))).toBe(true);
    expect(isChunkLoadError(new Error("ChunkLoadError: Loading chunk 1 failed"))).toBe(true);
    expect(isChunkLoadError(new Error("other error"))).toBe(false);
  });

  it("reloads only once for chunk failures", () => {
    expect(reloadForChunkErrorOnce(new Error("Failed to fetch dynamically imported module"), "test")).toBe(true);
    expect(reloadSpy).toHaveBeenCalledTimes(1);

    expect(reloadForChunkErrorOnce(new Error("Failed to fetch dynamically imported module"), "test")).toBe(false);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it("hooks vite preload errors into one-time reload recovery", () => {
    installChunkRecoveryHandlers();

    const event = new Event("vite:preloadError") as Event & {
      payload?: unknown;
      preventDefault: ReturnType<typeof vi.fn>;
    };
    event.payload = new Error("Failed to fetch dynamically imported module");
    event.preventDefault = vi.fn();

    window.dispatchEvent(event);

    expect(reloadSpy).toHaveBeenCalledTimes(1);
    expect(event.preventDefault).toHaveBeenCalledTimes(1);
  });

  it("clears the one-time reload marker after a lazy route resolves successfully", async () => {
    sessionStorage.setItem("zenstory:chunk-reload-once", "1");
    const LazyComponent = lazyRoute(
      async () => ({
        default: () => createElement("div", null, "Lazy route content"),
      }),
      "lazy-route-success",
    );

    render(
      createElement(
        Suspense,
        { fallback: createElement("div", null, "loading") },
        createElement(LazyComponent),
      ),
    );

    expect(await screen.findByText("Lazy route content")).toBeInTheDocument();
    expect(sessionStorage.getItem("zenstory:chunk-reload-once")).toBeNull();
  });
});
