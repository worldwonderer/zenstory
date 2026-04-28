import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocsSidebar } from '../DocsSidebar'

let currentPath = '/docs/getting-started/quick-start'
let currentLanguage = 'en'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useLocation: () => ({ pathname: currentPath }),
    Link: ({ to, onClick, children }: { to: string; onClick?: () => void; children?: React.ReactNode }) => (
      <a href={to} onClick={onClick}>
        {children}
      </a>
    ),
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      (
        {
          documentation: 'Documentation Center',
          menu: 'Menu',
          closeMenu: 'Close menu',
        } as Record<string, string>
      )[key] ?? fallback ?? key,
    i18n: {
      language: currentLanguage,
    },
  }),
}))

vi.mock('../DocsSearchInput', () => ({
  DocsSearchInput: ({ onResultClick }: { onResultClick?: () => void }) => (
    <button type="button" data-testid="docs-search-input" onClick={onResultClick}>
      Search
    </button>
  ),
}))

describe('DocsSidebar', () => {
  beforeEach(() => {
    currentPath = '/docs/getting-started/quick-start'
    currentLanguage = 'en'
  })

  it('renders navigation for the active docs path', () => {
    render(<DocsSidebar />)

    expect(screen.getAllByText('Documentation Center').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'Getting Started' })[0]).toHaveAttribute(
      'href',
      '/docs/getting-started/quick-start',
    )
    expect(screen.getAllByRole('link', { name: 'Quick Start' })[0]).toBeInTheDocument()
  })

  it('renders the mobile drawer and closes it from search or close button', () => {
    const onClose = vi.fn()
    render(<DocsSidebar isOpen={true} onClose={onClose} />)

    fireEvent.click(screen.getByRole('button', { name: 'Close menu' }))
    fireEvent.click(screen.getAllByTestId('docs-search-input')[1]!)

    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
