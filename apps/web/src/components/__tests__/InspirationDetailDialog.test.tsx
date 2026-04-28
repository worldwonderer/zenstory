import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { InspirationDetailDialog } from '../inspirations/InspirationDetailDialog'
import type { InspirationDetail } from '../../types'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown> | string) => {
      // Handle both string and object options
      const opt = typeof options === 'object' ? options : {}

      const translations: Record<string, string> = {
        // Project types (without prefix since useTranslation("inspirations") strips it)
        'projectTypes.novel': '长篇小说',
        'projectTypes.short': '短篇小说',
        'projectTypes.screenplay': '剧本',
        // Simple keys
        'community': '社区',
        'copyCount': `已复制 ${opt?.count ?? 0} 次`,
        'description': '描述',
        'tags': '标签',
        'fileStructure': '文件结构',
        'noFiles': '暂无文件',
        'projectName': '项目名称',
        'projectNameHint': '留空则使用灵感库名称',
        'cancel': '取消',
        'copied': '已复制',
        'copying': '复制中...',
        'useThis': '使用此模板',
      }
      return translations[key] ?? (typeof options === 'string' ? options : key)
    },
  }),
}))

// Mock icons
vi.mock('../icons', () => ({
  X: () => <span data-testid="icon-x">X</span>,
  Copy: () => <span data-testid="icon-copy">Copy</span>,
  Star: () => <span data-testid="icon-star">Star</span>,
  Users: () => <span data-testid="icon-users">Users</span>,
  FileText: () => <span data-testid="icon-filetext">FileText</span>,
  Check: () => <span data-testid="icon-check">Check</span>,
  FolderOpen: () => <span data-testid="icon-folderopen">FolderOpen</span>,
  Clapperboard: () => <span data-testid="icon-clapperboard">Clapperboard</span>,
  Globe: () => <span data-testid="icon-globe">Globe</span>,
  File: () => <span data-testid="icon-file">File</span>,
}))

const mockInspiration: InspirationDetail = {
  id: 'test-inspiration-1',
  name: 'Test Novel Template',
  description: 'A test novel template for unit testing',
  cover_image: 'https://example.com/cover.jpg',
  project_type: 'novel',
  tags: ['fantasy', 'adventure', 'magic'],
  source: 'community',
  author_id: 'author-1',
  original_project_id: 'project-1',
  copy_count: 42,
  is_featured: true,
  created_at: '2024-01-01T00:00:00Z',
  file_preview: [
    { title: 'Main Outline', file_type: 'outline', has_content: true },
    { title: 'Chapter 1', file_type: 'draft', has_content: true },
    { title: 'Hero Character', file_type: 'character', has_content: true },
    { title: 'World Lore', file_type: 'lore', has_content: false },
  ],
}

const mockMinimalInspiration: InspirationDetail = {
  id: 'test-inspiration-2',
  name: 'Minimal Template',
  description: null,
  cover_image: null,
  project_type: 'short',
  tags: [],
  source: 'official',
  author_id: null,
  original_project_id: null,
  copy_count: 0,
  is_featured: false,
  created_at: '2024-01-01T00:00:00Z',
  file_preview: [],
}

describe('InspirationDetailDialog', () => {
  const mockOnClose = vi.fn()
  const mockOnCopy = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    mockOnCopy.mockResolvedValue(undefined)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Dialog Open/Close', () => {
    it('renders nothing when isOpen is false', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={false}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders nothing when inspiration is null', () => {
      render(
        <InspirationDetailDialog
          inspiration={null}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders dialog when isOpen and inspiration are provided', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('calls onClose when backdrop is clicked', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const backdrop = screen.getByRole('dialog').parentElement
      fireEvent.click(backdrop!)

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when close button is clicked', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const closeButton = screen.getByLabelText('Close modal')
      fireEvent.click(closeButton!)

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when cancel button is clicked', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const cancelButton = screen.getByText('取消')
      fireEvent.click(cancelButton)

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('Inspiration Details Display', () => {
    it('displays inspiration name as title', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('Test Novel Template')).toBeInTheDocument()
    })

    it('displays star icon for featured inspirations', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByTestId('icon-star')).toBeInTheDocument()
    })

    it('does not display star icon for non-featured inspirations', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByTestId('icon-star')).not.toBeInTheDocument()
    })

    it('displays project type badge', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('长篇小说')).toBeInTheDocument()
    })

    it('displays community badge for community sources', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('社区')).toBeInTheDocument()
    })

    it('does not display community badge for official sources', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByText('社区')).not.toBeInTheDocument()
    })

    it('displays copy count', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('已复制 42 次')).toBeInTheDocument()
    })

    it('displays cover image when available', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const coverImage = screen.getByAltText('Test Novel Template')
      expect(coverImage).toBeInTheDocument()
      expect(coverImage).toHaveAttribute('src', 'https://example.com/cover.jpg')
    })

    it('does not display cover image when not available', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })

    it('displays description when available', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('A test novel template for unit testing')).toBeInTheDocument()
    })

    it('does not display description section when not available', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      // The description section should not be present
      expect(screen.queryByText('描述')).not.toBeInTheDocument()
    })

    it('displays tags when available', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('fantasy')).toBeInTheDocument()
      expect(screen.getByText('adventure')).toBeInTheDocument()
      expect(screen.getByText('magic')).toBeInTheDocument()
    })

    it('does not display tags section when empty', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.queryByText('标签')).not.toBeInTheDocument()
    })

    it('displays file preview list', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('Main Outline')).toBeInTheDocument()
      expect(screen.getByText('Chapter 1')).toBeInTheDocument()
      expect(screen.getByText('Hero Character')).toBeInTheDocument()
      expect(screen.getByText('World Lore')).toBeInTheDocument()
    })

    it('displays no files message when file preview is empty', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockMinimalInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('暂无文件')).toBeInTheDocument()
    })
  })

  describe('Project Name Input', () => {
    it('displays project name input field', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('项目名称')).toBeInTheDocument()
      expect(screen.getByPlaceholderText('Test Novel Template')).toBeInTheDocument()
    })

    it('displays hint text for project name', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      expect(screen.getByText('留空则使用灵感库名称')).toBeInTheDocument()
    })

    it('allows entering custom project name', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const input = screen.getByPlaceholderText('Test Novel Template')
      fireEvent.change(input, { target: { value: 'My Custom Project' } })

      expect(input).toHaveValue('My Custom Project')
    })

    it('resets project name when switching to another inspiration', () => {
      const nextInspiration: InspirationDetail = {
        ...mockInspiration,
        id: 'test-inspiration-2',
        name: 'Another Template',
      }

      const { rerender } = render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const input = screen.getByPlaceholderText('Test Novel Template')
      fireEvent.change(input, { target: { value: 'Temp Name' } })
      expect(input).toHaveValue('Temp Name')

      rerender(
        <InspirationDetailDialog
          inspiration={nextInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const nextInput = screen.getByPlaceholderText('Another Template')
      expect(nextInput).toHaveValue('')
    })
  })

  describe('Copy Button Functionality', () => {
    it('calls onCopy with inspiration id and project name', async () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const input = screen.getByPlaceholderText('Test Novel Template')
      fireEvent.change(input, { target: { value: 'My New Project' } })

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(mockOnCopy).toHaveBeenCalledWith('test-inspiration-1', 'My New Project')
      })
    })

    it('calls onCopy with undefined when project name is empty', async () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(mockOnCopy).toHaveBeenCalledWith('test-inspiration-1', undefined)
      })
    })

    it('shows copied state after successful copy', async () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(screen.getByText('已复制')).toBeInTheDocument()
      })
    })

    it('closes dialog after successful copy with delay', async () => {
      vi.useFakeTimers()

      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      // Wait for the async onCopy to complete
      await act(async () => {
        await vi.runAllTimersAsync()
      })

      // Should have called onClose after the timeout
      expect(mockOnClose).toHaveBeenCalledTimes(1)

      vi.useRealTimers()
    })

    it('handles copy error gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockOnCopy.mockRejectedValueOnce(new Error('Copy failed'))

      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled()
        expect(
          consoleErrorSpy.mock.calls.some((call) =>
            call.includes('Failed to copy inspiration:')
          )
        ).toBe(true)
      })

      consoleErrorSpy.mockRestore()
    })
  })

  describe('Loading State', () => {
    it('disables copy button when isCopying is true', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
          isCopying={true}
        />
      )

      const copyButton = screen.getByText('复制中...')
      expect(copyButton.closest('button')).toBeDisabled()
    })

    it('shows copying text when isCopying is true', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
          isCopying={true}
        />
      )

      expect(screen.getByText('复制中...')).toBeInTheDocument()
    })

    it('disables copy button during copy success state', async () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const copyButton = screen.getByText('使用此模板')
      fireEvent.click(copyButton)

      await waitFor(() => {
        expect(screen.getByText('已复制')).toBeInTheDocument()
      })

      // Button should be disabled during success state
      const successButton = screen.getByText('已复制').closest('button')
      expect(successButton).toBeDisabled()
    })
  })

  describe('Accessibility', () => {
    it('has proper dialog role and aria attributes', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(dialog).toHaveAttribute('aria-labelledby')
    })

    it('has accessible title via aria-labelledby', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      const title = screen.getByText('Test Novel Template')
      const dialog = screen.getByRole('dialog')
      const labelledBy = dialog.getAttribute('aria-labelledby')
      expect(labelledBy).toBeTruthy()
      const labelledElement = document.getElementById(labelledBy!)
      expect(labelledElement).toBeInTheDocument()
      expect(labelledElement).toContainElement(title)
    })

    it('has accessible copy button', () => {
      render(
        <InspirationDetailDialog
          inspiration={mockInspiration}
          isOpen={true}
          onClose={mockOnClose}
          onCopy={mockOnCopy}
        />
      )

      // Find the copy button by looking for the button containing "使用此模板"
      const copyButton = screen.getByText('使用此模板').closest('button')
      expect(copyButton).toBeInTheDocument()
    })
  })
})
