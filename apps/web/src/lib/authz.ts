/**
 * Lightweight authz helpers for the web app.
 *
 * NOTE:
 * - Prefer passing an explicit `user` when available.
 * - As a convenience (and to avoid wiring hooks everywhere), helpers may fall
 *   back to the cached user in localStorage.
 */

type AdminLikeUser = {
  is_superuser?: boolean;
};

/**
 * Returns true when the current user is an admin (superuser).
 */
export function isAdmin(user?: AdminLikeUser | null): boolean {
  if (user) return Boolean(user.is_superuser);

  if (typeof window === "undefined") return false;

  try {
    const raw = localStorage.getItem("user");
    if (!raw) return false;
    const cached = JSON.parse(raw) as AdminLikeUser | null;
    return Boolean(cached?.is_superuser);
  } catch {
    return false;
  }
}

