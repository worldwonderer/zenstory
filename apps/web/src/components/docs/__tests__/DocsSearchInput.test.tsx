import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DocsSearchInput } from '../DocsSearchInput'

const mockNavigate = vi.fn()
const mockClearSearch = vi.fn()
let currentLanguage = 'en'
let currentResults = [
  {
    title: 'Quick Start',
    titleZh: '5分钟快速入门',
    path: '/docs/getting-started/quick-start',
    parentTitle: 'Getting Started',
    parentTitleZh: '快速入门',
    score: 4,
  },
]
let currentSearching = false

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) =>
      (
        {
          searchPlaceholder: 'Search documentation',
          loading: 'Loading...',
          noResults: 'No results',
        } as Record<string, string>
      )[key] ?? fallback ?? key,
    i18n: {
      language: currentLanguage,
    },
  }),
}))

vi.mock('../../../hooks/useDocsSearch', () => ({
  useDocsSearch: ({ query }: { query: string }) => ({
    results: query ? currentResults : [],
    isSearching: currentSearching,
    clearSearch: mockClearSearch,
  }),
}))

describe('DocsSearchInput', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentLanguage = 'en'
    currentResults = [
      {
        title: 'Quick Start',
        titleZh: '5分钟快速入门',
        path: '/docs/getting-started/quick-start',
        parentTitle: 'Getting Started',
        parentTitleZh: '快速入门',
        score: 4,
      },
    ]
    currentSearching = false
  })

  it('renders search results and navigates when a result is selected', async () => {
    const onResultClick = vi.fn()
    render(<DocsSearchInput onResultClick={onResultClick} />)

    const input = screen.getByPlaceholderText('Search documentation')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'quick' } })

    const resultButton = await screen.findByRole('button', { name: /Quick Start/i })
    fireEvent.click(resultButton)

    expect(mockNavigate).toHaveBeenCalledWith('/docs/getting-started/quick-start')
    expect(mockClearSearch).toHaveBeenCalled()
    expect(onResultClick).toHaveBeenCalled()
  })

  it('supports keyboard shortcuts and clears the query', async () => {
    render(<DocsSearchInput />)

    const input = screen.getByPlaceholderText('Search documentation')
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    await waitFor(() => expect(input).toHaveFocus())

    fireEvent.change(input, { target: { value: 'quick' } })
    fireEvent.keyDown(document, { key: 'Escape' })

    expect(mockClearSearch).toHaveBeenCalled()
    expect(input).toHaveValue('')
  })

  it('renders a no-results state and translated titles', () => {
    currentLanguage = 'zh'
    currentResults = []

    render(<DocsSearchInput />)

    const input = screen.getByPlaceholderText('Search documentation')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: '快速' } })

    expect(screen.getByText('No results')).toBeInTheDocument()
  })
})
