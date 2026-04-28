import { describe, expect, it, vi } from 'vitest';

vi.mock('../apiClient', () => ({
  tryRefreshToken: vi.fn(),
  validateToken: vi.fn(),
}));

vi.mock('../logger', () => ({
  logger: {
    log: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

import { isValidRedirectUrl } from '../ssoRedirect';

describe('isValidRedirectUrl', () => {
  it('accepts zenstory subdomain redirect', () => {
    expect(isValidRedirectUrl('https://app.zenstory.ai/projects')).toBe(true);
  });

  it('accepts zenstory subdomains', () => {
    expect(isValidRedirectUrl('https://app.zenstory.ai/workspace')).toBe(true);
  });

  it('rejects non-http protocols', () => {
    expect(isValidRedirectUrl('ftp://zenstory.ai/resource')).toBe(false);
  });

  it('rejects redirects with userinfo', () => {
    expect(isValidRedirectUrl('https://user@zenstory.ai/callback')).toBe(false);
  });

  it('rejects non-whitelisted domains', () => {
    expect(isValidRedirectUrl('https://evil.example.com/callback')).toBe(false);
  });
});
