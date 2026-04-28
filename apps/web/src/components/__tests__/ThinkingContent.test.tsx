import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThinkingContent } from '../ThinkingContent'

vi.mock('../LazyMarkdown', async () => {
  const ReactMarkdown = (await import('react-markdown')).default
  const remarkGfm = (await import('remark-gfm')).default

  const SyncMarkdown = ({
    children,
    className,
  }: {
    children: string
    className?: string
  }) => (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )

  return {
    LazyMarkdown: SyncMarkdown,
    default: SyncMarkdown,
  }
})

// Import the mocked module type
import { useThinkingVisibility } from '../../hooks/useThinkingVisibility'

// Mock the useThinkingVisibility hook
vi.mock('../../hooks/useThinkingVisibility', () => ({
  useThinkingVisibility: vi.fn(() => ({
    showThinking: true,
    setShowThinking: vi.fn(),
    toggleThinking: vi.fn(),
  })),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

describe('ThinkingContent', () => {
  beforeEach(() => {
    // Clear localStorage completely before each test
    localStorage.clear()
    // Reset mocks
    vi.clearAllMocks()
    // Reset the mock to default behavior
    vi.mocked(useThinkingVisibility).mockReturnValue({
      showThinking: true,
      setShowThinking: vi.fn(),
      toggleThinking: vi.fn(),
    })
  })

  afterEach(() => {
    // Clean up localStorage after each test
    localStorage.clear()
  })

  it('returns null when content is only whitespace', () => {
    // Use template literal with explicit whitespace characters
    const whitespaceContent = '   \n\t  '
    const { container } = render(<ThinkingContent content={whitespaceContent} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders thinking text', async () => {
    // Set to expanded state
    localStorage.setItem('zenstory_thinking_expanded', 'true')

    render(<ThinkingContent content="Analyzing your request..." />)
    expect(screen.getByText('chat:thinking.title')).toBeInTheDocument()
    expect(screen.getByText('Analyzing your request...')).toBeInTheDocument()
  })

  it('returns null when content is empty', () => {
    const { container } = render(<ThinkingContent content="" />)
    expect(container.firstChild).toBeNull()
  })

  it('toggles visibility when clicked', async () => {
    const user = userEvent.setup()
    // Start expanded
    localStorage.setItem('zenstory_thinking_expanded', 'true')

    render(<ThinkingContent content="Thinking process" />)

    const button = screen.getByRole('button')
    // Content should be visible initially
    expect(screen.getByText('Thinking process')).toBeInTheDocument()

    // Click to collapse
    await act(async () => {
      await user.click(button)
    })

    await waitFor(() => {
      expect(screen.queryByText('Thinking process')).not.toBeInTheDocument()
    })

    // Click to expand again
    await act(async () => {
      await user.click(button)
    })

    await waitFor(() => {
      expect(screen.getByText('Thinking process')).toBeInTheDocument()
    })
  })

  it('collapses by default when localStorage is false', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'false')

    render(<ThinkingContent content="Thinking process" />)

    // Should be collapsed - content not visible
    expect(screen.queryByText('Thinking process')).not.toBeInTheDocument()
  })

  it('expands by default when localStorage is true', () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')

    render(<ThinkingContent content="Thinking process" />)

    // Should be expanded
    expect(screen.getByText('Thinking process')).toBeInTheDocument()
  })

  it('persists expand/collapse state to localStorage', async () => {
    const user = userEvent.setup()
    // Start expanded
    localStorage.setItem('zenstory_thinking_expanded', 'true')

    render(<ThinkingContent content="Thinking process" />)

    const button = screen.getByRole('button')

    // Click to collapse
    await act(async () => {
      await user.click(button)
    })

    // Check localStorage was updated
    await waitFor(() => {
      expect(localStorage.getItem('zenstory_thinking_expanded')).toBe('false')
    })
  })

  it('shows streaming dots when isStreaming is true', () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="Thinking..." isStreaming={true} />)

    // Animated dots should be present
    const container = screen.getByText('chat:thinking.title').parentElement
    const dots = container?.querySelectorAll('.animate-pulse')
    expect(dots?.length || 0).toBeGreaterThan(0)
  })

  it('does not show streaming dots when isStreaming is false', () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="Thinking..." isStreaming={false} />)

    // No animated dots in the button area
    const titleElement = screen.getByText('chat:thinking.title')
    const container = titleElement.parentElement
    const dots = container?.querySelectorAll('.animate-pulse')
    expect(dots?.length || 0).toBe(0)
  })

  it('renders markdown content', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    const content = `# Analysis

- Point 1
- Point 2`
    render(<ThinkingContent content={content} />)

    // Content should be visible
    expect(screen.getByRole('heading', { name: 'Analysis' })).toBeInTheDocument()
    expect(screen.getByText('Point 1')).toBeInTheDocument()
    expect(screen.getByText('Point 2')).toBeInTheDocument()
  })

  it('renders bold markdown text', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="This is **important** thinking" />)

    const strongElement = screen.getByText('important')
    expect(strongElement.tagName).toBe('STRONG')
  })

  it('renders italic markdown text', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="This is *emphasized* thinking" />)

    const emElement = screen.getByText('emphasized')
    expect(emElement.tagName).toBe('EM')
  })

  it('renders code blocks in markdown', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="Use `code` here" />)

    const codeElement = screen.getByText('code')
    expect(codeElement.tagName).toBe('CODE')
  })

  it('renders links in markdown', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="See [docs](https://example.com)" />)

    const link = screen.getByRole('link', { name: 'docs' })
    expect(link).toHaveAttribute('href', 'https://example.com')
  })

  it('renders lists in markdown', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    const content = `- Item 1
- Item 2
- Item 3`
    render(<ThinkingContent content={content} />)

    expect(screen.getByText('Item 1')).toBeInTheDocument()
    expect(screen.getByText('Item 2')).toBeInTheDocument()
    expect(screen.getByText('Item 3')).toBeInTheDocument()
  })

  it('has correct aria-label for expand button', async () => {
    // Start collapsed
    localStorage.setItem('zenstory_thinking_expanded', 'false')
    render(<ThinkingContent content="Thinking process" />)

    const button = screen.getByRole('button')
    // When collapsed, aria-label should be 'expand'
    expect(button).toHaveAttribute('aria-label', 'chat:thinking.expand')
  })

  it('has correct aria-label for collapse button', () => {
    // Start expanded
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="Thinking process" />)

    const button = screen.getByRole('button')
    // When expanded, aria-label should be 'collapse'
    expect(button).toHaveAttribute('aria-label', 'chat:thinking.collapse')
  })

  it('applies hover opacity transition', () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    const { container } = render(<ThinkingContent content="Thinking" />)

    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain('opacity-60')
    expect(wrapper.className).toContain('hover:opacity-80')
  })

  it('returns null when showThinking is false', () => {
    // Override the mock for this specific test
    vi.mocked(useThinkingVisibility).mockReturnValue({
      showThinking: false,
      setShowThinking: vi.fn(),
      toggleThinking: vi.fn(),
    })

    const { container } = render(<ThinkingContent content="Thinking" />)
    expect(container.firstChild).toBeNull()
  })

  it('handles long content', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    const longContent = 'A'.repeat(1000)
    render(<ThinkingContent content={longContent} />)

    // The content should be displayed (may be broken up by markdown rendering)
    const contentArea = screen.getByText(/A+/)
    expect(contentArea).toBeInTheDocument()
  })

  it('handles multiline content', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    const multilineContent = `Line 1
Line 2
Line 3`
    render(<ThinkingContent content={multilineContent} />)

    // Check for at least one line
    expect(screen.getByText(/Line 1/)).toBeInTheDocument()
  })

  it('shows chevron icon pointing up when expanded', () => {
    localStorage.setItem('zenstory_thinking_expanded', 'true')
    render(<ThinkingContent content="Thinking" />)

    // Check for chevron icon
    const button = screen.getByRole('button')
    const chevron = button.querySelector('svg')
    expect(chevron).toBeInTheDocument()
    // Check it's the up chevron by checking the path
    expect(chevron?.innerHTML).toContain('m18 15-6-6-6 6')
  })

  it('shows chevron icon pointing down when collapsed', async () => {
    localStorage.setItem('zenstory_thinking_expanded', 'false')
    render(<ThinkingContent content="Thinking" />)

    const button = screen.getByRole('button')
    const chevron = button.querySelector('svg')
    expect(chevron).toBeInTheDocument()
    // Check it's the down chevron by checking the path
    expect(chevron?.innerHTML).toContain('m6 9 6 6 6-6')
  })
})
