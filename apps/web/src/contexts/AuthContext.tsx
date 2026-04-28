import React, { createContext, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi } from '../lib/api';
import type { UserSubscription, UsageQuota } from '../types/subscription';
import { logger } from '../lib/logger';
import { tryRefreshToken as tryRefreshTokenSingleFlight } from '../lib/apiClient';
import { identifyUser, resetAnalytics, trackEvent } from '../lib/analytics';

export interface User {
  id: string;
  username: string;
  email: string;
  email_verified: boolean;
  avatar_url?: string;
  nickname?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  subscription?: UserSubscription;
  quota?: UsageQuota;
}

export interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, inviteCode?: string) => Promise<{ email: string; email_verified: boolean }>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  handleOAuthCallback: (accessToken: string, refreshToken: string) => Promise<void>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  resendVerification: (email: string) => Promise<void>;
  googleLogin: (options?: { inviteCode?: string; redirectUrl?: string }) => void;
  appleLogin: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Cache TTL: 5 minutes (conservative to balance performance and security)
const AUTH_CACHE_TTL_MS = 5 * 60 * 1000;

// Cache keys
const CACHE_KEYS = {
  USER: 'user',
  VALIDATED_AT: 'auth_validated_at',
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
} as const;

// Helper to clear auth state (including cache)
const clearAuthState = (setUser: (user: User | null) => void) => {
  localStorage.removeItem(CACHE_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(CACHE_KEYS.REFRESH_TOKEN);
  localStorage.removeItem(CACHE_KEYS.USER);
  localStorage.removeItem(CACHE_KEYS.VALIDATED_AT);
  setUser(null);
};

// Helper to save user cache with timestamp
const saveUserCache = (userData: User) => {
  try {
    localStorage.setItem(CACHE_KEYS.USER, JSON.stringify(userData));
    localStorage.setItem(CACHE_KEYS.VALIDATED_AT, Date.now().toString());
  } catch {
    logger.warn('[Auth] Failed to save user cache (localStorage may be unavailable)');
  }
};

// Helper to read cached user if valid (within TTL)
const getValidCachedUser = (): User | null => {
  try {
    const cachedUserStr = localStorage.getItem(CACHE_KEYS.USER);
    const lastValidatedStr = localStorage.getItem(CACHE_KEYS.VALIDATED_AT);

    if (!cachedUserStr || !lastValidatedStr) {
      return null;
    }

    const lastValidated = parseInt(lastValidatedStr, 10);
    const now = Date.now();

    // Check if cache is still within TTL
    if (now - lastValidated < AUTH_CACHE_TTL_MS) {
      return JSON.parse(cachedUserStr) as User;
    }

    return null;
  } catch {
    logger.warn('[Auth] Failed to read user cache (corrupted data)');
    return null;
  }
};

// Helper to attempt token refresh
const attemptTokenRefresh = async (setUser: (user: User | null) => void): Promise<boolean> => {
  const refreshed = await tryRefreshTokenSingleFlight();
  if (!refreshed) return false;

  // tryRefreshTokenSingleFlight already persisted tokens + user cache.
  const cachedUserStr = localStorage.getItem(CACHE_KEYS.USER);
  if (cachedUserStr) {
    try {
      const cachedUser = JSON.parse(cachedUserStr) as User;
      setUser(cachedUser);
    } catch {
      // Corrupted cache - fallback to unauthenticated state.
      setUser(null);
    }
  }

  return true;
};

// Background validation - doesn't block UI, updates cache silently
const validateTokenInBackground = async (
  accessToken: string,
  setUser: (user: User | null) => void
): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { 'Authorization': `Bearer ${accessToken}` },
    });

    if (response.ok) {
      const serverUser = await response.json();
      setUser(serverUser);
      saveUserCache(serverUser);
      logger.log('[Auth] Background validation succeeded');
    } else {
      // Token invalid in background - clear silently
      logger.warn('[Auth] Background validation failed: token invalid');
      clearAuthState(setUser);
    }
  } catch (error) {
    // Background validation failed - don't disrupt UX
    logger.warn('[Auth] Background validation failed (network error):', error);
  }
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const previousUserIdRef = React.useRef<string | null>(null);

  // Initialize user from localStorage on mount with validation
  // Cache Strategy: Use cached user within TTL for instant load, validate in background
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const accessToken = localStorage.getItem(CACHE_KEYS.ACCESS_TOKEN);
        const refreshToken = localStorage.getItem(CACHE_KEYS.REFRESH_TOKEN);

        // No token at all - nothing to validate, clear any stale cache
        if (!accessToken) {
          clearAuthState(setUser);
          return;
        }

        // Check for valid cached user (within TTL)
        const cachedUser = getValidCachedUser();

        if (cachedUser) {
          // Cache hit and valid - immediately set user for fast initial render
          logger.log('[Auth] Using cached user (within TTL)');
          setUser(cachedUser);
          setLoading(false);

          // Validate token in background to ensure freshness
          // This doesn't block the UI - user sees cached data immediately
          validateTokenInBackground(accessToken, setUser);
          return;
        }

        // Cache miss or expired - normal validation flow
        logger.log('[Auth] Cache miss or expired, validating token...');
        try {
          const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${accessToken}` },
          });

          if (response.ok) {
            // Token valid - use server response and cache it
            const serverUser = await response.json();
            saveUserCache(serverUser);
            setUser(serverUser);
            logger.log('[Auth] Token validated on init');
          } else {
            // Token invalid - try refresh
            logger.log('[Auth] Token invalid on init, attempting refresh...');
            if (refreshToken) {
              const refreshed = await attemptTokenRefresh(setUser);
              if (refreshed) {
                logger.log('[Auth] Token refreshed on init');
              } else {
                logger.warn('[Auth] Token refresh failed on init, clearing state');
                clearAuthState(setUser);
              }
            } else {
              clearAuthState(setUser);
            }
          }
        } catch {
          // Network error - avoid cached user to prevent stale SSO state,
          // but preserve tokens because the failure may be transient.
          logger.warn('[Auth] Network error during init, marking unauthenticated without clearing tokens');
          setUser(null);
        }
      } catch (error) {
        logger.error('Failed to initialize auth:', error);
        clearAuthState(setUser);
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, []);

  // Keep auth state in sync when API client clears tokens (same-tab)
  useEffect(() => {
    const onLogout = () => {
      logger.log('[Auth] Logout event received');
      setUser(null);
    };

    window.addEventListener('auth:logout', onLogout as EventListener);
    return () => {
      window.removeEventListener('auth:logout', onLogout as EventListener);
    };
  }, []);

  useEffect(() => {
    if (loading) return;

    if (user) {
      identifyUser(user);
      previousUserIdRef.current = user.id;
      return;
    }

    if (previousUserIdRef.current) {
      resetAnalytics();
      previousUserIdRef.current = null;
    }
  }, [loading, user]);

  const login = async (username: string, password: string) => {
    const data = await authApi.login(username, password);

    // Store tokens and user data with cache timestamp
    localStorage.setItem(CACHE_KEYS.ACCESS_TOKEN, data.access_token);
    localStorage.setItem(CACHE_KEYS.REFRESH_TOKEN, data.refresh_token);
    saveUserCache(data.user);

    setUser(data.user);
    trackEvent('login_success', {
      login_method: 'password',
      is_superuser: data.user.is_superuser,
    });
  };

  const register = async (username: string, email: string, password: string, inviteCode?: string) => {
    const data = await authApi.register({ username, email, password, invite_code: inviteCode });
    trackEvent('register_success', {
      email_verified: data.email_verified,
      invite_code_provided: Boolean(inviteCode?.trim()),
    });

    // Return email and verification status for redirect
    return {
      email: data.email,
      email_verified: data.email_verified
    };
  };

  const logout = () => {
    trackEvent('logout');
    resetAnalytics();
    // Clear all auth data including cache
    clearAuthState(setUser);
  };

  const verifyEmail = async (email: string, code: string) => {
    const data = await authApi.verifyEmail(email, code);

    // Store tokens and user data with cache timestamp
    localStorage.setItem(CACHE_KEYS.ACCESS_TOKEN, data.access_token);
    localStorage.setItem(CACHE_KEYS.REFRESH_TOKEN, data.refresh_token);
    saveUserCache(data.user);

    setUser(data.user);
    trackEvent('verify_email_success', {
      email_verified: data.user.email_verified,
    });
  };

  const resendVerification = async (email: string) => {
    return await authApi.resendVerification(email);
  };

  const refreshToken = async () => {
    const refreshToken = localStorage.getItem(CACHE_KEYS.REFRESH_TOKEN);
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const data = await authApi.refreshToken(refreshToken);

      // Update tokens and cache
      localStorage.setItem(CACHE_KEYS.ACCESS_TOKEN, data.access_token);
      localStorage.setItem(CACHE_KEYS.REFRESH_TOKEN, data.refresh_token);
      saveUserCache(data.user);

      setUser(data.user);
    } catch (error) {
      // If refresh fails, logout
      logout();
      throw error;
    }
  };

  const handleOAuthCallback = async (accessToken: string, refreshToken: string) => {
    // After OAuth callback, we need to fetch user info using the access token
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      logout();
      throw new Error('Failed to fetch user info');
    }

    const user = await response.json();

    // Store tokens and user data with cache timestamp
    localStorage.setItem(CACHE_KEYS.ACCESS_TOKEN, accessToken);
    localStorage.setItem(CACHE_KEYS.REFRESH_TOKEN, refreshToken);
    saveUserCache(user);

    setUser(user);
    trackEvent('oauth_callback_success');
  };

  const googleLogin = (options?: { inviteCode?: string; redirectUrl?: string }) => {
    // Check for redirect parameter from external apps
    const params = new URLSearchParams(window.location.search);
    const redirectUrl = options?.redirectUrl ?? params.get('redirect');
    const inviteCode = options?.inviteCode?.trim();

    // Redirect to backend Google OAuth endpoint
    const googleAuthUrl = `${API_BASE}/api/auth/google`;
    const url = new URL(googleAuthUrl);

    if (redirectUrl) {
      // Pass redirect parameter to backend OAuth flow
      url.searchParams.set('redirect', redirectUrl);
    }
    if (inviteCode) {
      // Pass invite code for new-user gating (especially when registration requires invite codes)
      url.searchParams.set('invite_code', inviteCode);
    }

    window.location.href = url.toString();
  };

  /**
   * Apple OAuth login - pending backend implementation.
   *
   * @feature_request Sign in with Apple support
   * @backend_needed Add /api/v1/auth/apple endpoint with Apple ID integration
   * @see https://developer.apple.com/sign-in-with-apple/
   * @see apps/server/api/auth.py for OAuth implementation reference
   */
  const appleLogin = () => {
    logger.log('Apple OAuth coming soon');
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshToken, handleOAuthCallback, verifyEmail, resendVerification, googleLogin, appleLogin }}>
      {children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
