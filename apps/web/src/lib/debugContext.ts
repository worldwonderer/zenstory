export interface DebugContextSnapshot {
  trace_id?: string;
  request_id?: string;
  agent_run_id?: string;
  project_id?: string;
  agent_session_id?: string | null;
  route?: string;
  created_at?: string;
}

const STORAGE_KEY = "zenstory_debug_context_v1";

const safeParse = (raw: string | null): DebugContextSnapshot | null => {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    return parsed as DebugContextSnapshot;
  } catch {
    return null;
  }
};

export const debugContext = {
  get(): DebugContextSnapshot | null {
    if (typeof window === "undefined") return null;
    return safeParse(window.sessionStorage.getItem(STORAGE_KEY));
  },

  set(snapshot: DebugContextSnapshot): void {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
    } catch {
      // ignore quota/security errors
    }
  },

  clear(): void {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  },
};

