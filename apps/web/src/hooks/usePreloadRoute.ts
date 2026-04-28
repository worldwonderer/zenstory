/**
 * Route preloading utilities
 * Used to preload route components on mouse hover for improved user experience
 */

import { useCallback } from "react";

/** Cache for storing preloaded route promises */
const preloadCache = new Map<string, Promise<unknown>>();

/**
 * Preload a route component
 *
 * @param importFn - Dynamic import function for the route component
 * @param key - Cache key (typically the route path)
 *
 * @example
 * ```ts
 * // Preload the dashboard route
 * preloadRoute(() => import('./pages/Dashboard'), '/dashboard');
 * ```
 */
export function preloadRoute(
  importFn: () => Promise<unknown>,
  key: string
): void {
  // Skip if already preloaded
  if (preloadCache.has(key)) {
    return;
  }

  // Start preloading
  const preloadPromise = importFn();
  preloadCache.set(key, preloadPromise);
}

/**
 * Hook for preloading route components on user interaction
 *
 * @param importFn - Dynamic import function for the route component
 * @param key - Cache key (typically the route path)
 * @returns Preload handler function to attach to event listeners
 *
 * @example
 * ```tsx
 * // Basic usage with onMouseEnter
 * const handlePreload = usePreloadRoute(
 *   () => import('./pages/Dashboard'),
 *   '/dashboard'
 * );
 *
 * return (
 *   <Link to="/dashboard" onMouseEnter={handlePreload}>
 *     Dashboard
 *   </Link>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // Usage with a navigation menu
 * const routes = [
 *   { path: '/settings', label: 'Settings', import: () => import('./pages/Settings') },
 *   { path: '/profile', label: 'Profile', import: () => import('./pages/Profile') },
 * ];
 *
 * function NavItem({ route }) {
 *   const handlePreload = usePreloadRoute(route.import, route.path);
 *   return (
 *     <Link to={route.path} onMouseEnter={handlePreload}>
 *       {route.label}
 *     </Link>
 *   );
 * }
 * ```
 */
export function usePreloadRoute(
  importFn: () => Promise<unknown>,
  key: string
): () => void {
  const handlePreload = useCallback(() => {
    preloadRoute(importFn, key);
  }, [importFn, key]);

  return handlePreload;
}
