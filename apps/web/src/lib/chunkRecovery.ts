import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { logger } from "./logger";

const CHUNK_RELOAD_STORAGE_KEY = "zenstory:chunk-reload-once";
const DYNAMIC_IMPORT_ERROR_PATTERNS = [
  "Failed to fetch dynamically imported module",
  "Importing a module script failed",
  "ChunkLoadError",
];

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message || String(error);
  }
  return String(error ?? "");
}

export function isChunkLoadError(error: unknown): boolean {
  const message = getErrorMessage(error);
  return DYNAMIC_IMPORT_ERROR_PATTERNS.some((pattern) => message.includes(pattern));
}

export function reloadForChunkErrorOnce(error: unknown, source: string): boolean {
  if (typeof window === "undefined" || !isChunkLoadError(error)) {
    return false;
  }

  const alreadyReloaded = sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY) === "1";
  if (alreadyReloaded) {
    sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);
    return false;
  }

  logger.warn("Recovering from stale chunk load failure", {
    source,
    message: getErrorMessage(error),
  });
  sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, "1");
  window.location.reload();
  return true;
}

export function installChunkRecoveryHandlers(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.addEventListener("vite:preloadError", (event) => {
    const viteEvent = event as Event & {
      payload?: unknown;
      preventDefault?: () => void;
    };
    if (reloadForChunkErrorOnce(viteEvent.payload ?? event, "vite:preloadError")) {
      viteEvent.preventDefault?.();
    }
  });

  window.addEventListener("unhandledrejection", (event) => {
    if (reloadForChunkErrorOnce(event.reason, "unhandledrejection")) {
      event.preventDefault();
    }
  });
}

export function lazyRoute<TProps>(
  importer: () => Promise<{ default: ComponentType<TProps> }>,
  source: string,
): LazyExoticComponent<ComponentType<TProps>> {
  return lazy(async () => {
    try {
      const module = await importer();
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(CHUNK_RELOAD_STORAGE_KEY);
      }
      return module;
    } catch (error) {
      if (reloadForChunkErrorOnce(error, source)) {
        return new Promise<never>(() => {});
      }
      throw error;
    }
  });
}
