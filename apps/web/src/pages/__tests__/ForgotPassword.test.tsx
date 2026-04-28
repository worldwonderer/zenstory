import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ForgotPassword from '../ForgotPassword'

let forgotPasswordEnabled = true

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    Link: ({ to, children }: { to: string; children?: React.ReactNode }) => <a href={to}>{children}</a>,
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate">{to}</div>,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      (
        {
          'auth:forgotPassword.title': 'Reset password',
          'auth:forgotPassword.subtitle': 'Contact support to reset your password',
          'auth:forgotPassword.contactSupportTitle': 'Need help?',
          'auth:forgotPassword.contactSupportHint': 'Reach out to support for manual assistance.',
          'auth:forgotPassword.contactSupportAction': 'Email support',
          'auth:forgotPassword.supportEmail': 'support@zenstory.ai',
          'auth:login.backToLogin': 'Back to login',
        } as Record<string, string>
      )[key] ?? fallback ?? key,
  }),
}))

vi.mock('../../components/PublicHeader', () => ({
  PublicHeader: () => <div data-testid="public-header">Header</div>,
}))

vi.mock('../../components/Logo', () => ({
  LogoMark: () => <div data-testid="logo-mark">Logo</div>,
}))

vi.mock('../../config/auth', () => ({
  authConfig: {
    get forgotPasswordEnabled() {
      return forgotPasswordEnabled
    },
  },
}))

describe('ForgotPassword', () => {
  beforeEach(() => {
    forgotPasswordEnabled = true
  })

  it('renders the support email flow when forgot password is enabled', () => {
    render(<ForgotPassword />)

    expect(screen.getByTestId('public-header')).toBeInTheDocument()
    expect(screen.getByText('Reset password')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to login' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('link', { name: 'Email support' })).toHaveAttribute(
      'href',
      'mailto:support@zenstory.ai',
    )
  })

  it('redirects back to login when the feature is disabled', () => {
    forgotPasswordEnabled = false
    render(<ForgotPassword />)

    expect(screen.getByTestId('navigate')).toHaveTextContent('/login')
  })
})
