import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { InspirationCard } from '../inspirations/InspirationCard'
import type { Inspiration } from '../../types'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown> | string) => {
      // Handle case where second arg is defaultValue string
      const opts = typeof options === 'object' ? options : {}

      const translations: Record<string, string> = {
        'projectTypes.novel': '长篇小说',
        'projectTypes.short': '短篇小说',
        'projectTypes.screenplay': '剧本',
        'heroHints.novel': '长篇叙事模板',
        'heroHints.short': '短篇灵感模板',
        'heroHints.screenplay': '剧本结构模板',
        'community': '社区',
        'featured': '精选',
        'copyCount': `复制 ${opts?.count ?? 0} 次`,
        'view': '查看',
        'use': '使用',
        'copying': '复制中...',
      }
      return translations[key] ?? key
    },
  }),
}))

// Mock icons
vi.mock('../icons', () => ({
  Copy: () => <svg data-testid="copy-icon" />,
  Users: () => <svg data-testid="users-icon" />,
}))

const mockInspiration: Inspiration = {
  id: 'test-inspiration-1',
  name: 'Test Inspiration',
  description: 'A test inspiration description',
  cover_image: 'https://example.com/cover.jpg',
  project_type: 'novel',
  tags: ['fantasy', 'adventure', 'magic'],
  source: 'official',
  author_id: null,
  original_project_id: null,
  copy_count: 42,
  is_featured: false,
  created_at: '2025-01-01T00:00:00Z',
}

describe('InspirationCard', () => {
  describe('Basic Rendering', () => {
    it('renders inspiration name correctly', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      expect(screen.getByText('Test Inspiration')).toBeInTheDocument()
    })

    it('renders description when provided', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      expect(screen.getAllByText('A test inspiration description').length).toBeGreaterThanOrEqual(1)
    })

    it('renders cover image when provided', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      const img = screen.getByRole('img', { name: 'Test Inspiration' })
      expect(img).toBeInTheDocument()
      expect(img).toHaveAttribute('src', 'https://example.com/cover.jpg')
    })

    it('renders placeholder media when no cover image', () => {
      const inspiration = { ...mockInspiration, cover_image: null }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByTestId('inspiration-card-placeholder')).toBeInTheDocument()
      expect(screen.queryByText('点击查看详情')).not.toBeInTheDocument()
    })

    it('renders project type label', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      expect(screen.getByText('长篇小说')).toBeInTheDocument()
    })
  })

  describe('Tags Display', () => {
    it('renders tags when provided', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      expect(screen.getByText('fantasy')).toBeInTheDocument()
      expect(screen.getByText('adventure')).toBeInTheDocument()
      expect(screen.getByText('magic')).toBeInTheDocument()
    })

    it('limits tags to 3 with overflow indicator', () => {
      const inspiration = {
        ...mockInspiration,
        tags: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'],
      }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('tag1')).toBeInTheDocument()
      expect(screen.getByText('tag2')).toBeInTheDocument()
      expect(screen.getByText('tag3')).toBeInTheDocument()
      expect(screen.getByText('+2')).toBeInTheDocument()
      expect(screen.queryByText('tag4')).not.toBeInTheDocument()
      expect(screen.queryByText('tag5')).not.toBeInTheDocument()
    })

    it('renders no tags when tags array is empty', () => {
      const inspiration = { ...mockInspiration, tags: [] }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.queryByText('fantasy')).not.toBeInTheDocument()
    })
  })

  describe('Copy Count Display', () => {
    it('displays copy count correctly', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      expect(screen.getByText('复制 42 次')).toBeInTheDocument()
    })

    it('displays zero copy count', () => {
      const inspiration = { ...mockInspiration, copy_count: 0 }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('复制 0 次')).toBeInTheDocument()
    })

    it('renders copy icon', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      // Copy icon appears twice: once in footer for copy count, once in use button
      const copyIcons = screen.getAllByTestId('copy-icon')
      expect(copyIcons.length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('Source Badge', () => {
    it('shows community badge for community source', () => {
      const inspiration = { ...mockInspiration, source: 'community' as const }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('社区')).toBeInTheDocument()
      expect(screen.getByTestId('users-icon')).toBeInTheDocument()
    })

    it('hides community badge for official source', () => {
      const inspiration = { ...mockInspiration, source: 'official' as const }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.queryByText('社区')).not.toBeInTheDocument()
    })
  })

  describe('Featured Badge', () => {
    it('shows featured badge for featured inspiration', () => {
      const inspiration = { ...mockInspiration, is_featured: true }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('精选')).toBeInTheDocument()
    })

    it('hides featured badge for non-featured inspiration', () => {
      const inspiration = { ...mockInspiration, is_featured: false }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.queryByText('精选')).not.toBeInTheDocument()
    })
  })

  describe('Click Interactions', () => {
    it('calls onView when title is clicked', () => {
      const onView = vi.fn()
      render(<InspirationCard inspiration={mockInspiration} onView={onView} />)

      fireEvent.click(screen.getByText('Test Inspiration'))

      expect(onView).toHaveBeenCalledTimes(1)
      expect(onView).toHaveBeenCalledWith('test-inspiration-1')
    })

    it('calls onView when cover image is clicked', () => {
      const onView = vi.fn()
      render(<InspirationCard inspiration={mockInspiration} onView={onView} />)

      const img = screen.getByRole('img', { name: 'Test Inspiration' })
      fireEvent.click(img.parentElement as HTMLElement)

      expect(onView).toHaveBeenCalledTimes(1)
      expect(onView).toHaveBeenCalledWith('test-inspiration-1')
    })

    it('calls onView when placeholder is clicked', () => {
      const onView = vi.fn()
      const inspiration = { ...mockInspiration, cover_image: null }
      render(<InspirationCard inspiration={inspiration} onView={onView} />)

      fireEvent.click(screen.getByTestId('inspiration-card-placeholder'))

      expect(onView).toHaveBeenCalledTimes(1)
      expect(onView).toHaveBeenCalledWith('test-inspiration-1')
    })

    it('calls onView when view button is clicked', () => {
      const onView = vi.fn()
      render(<InspirationCard inspiration={mockInspiration} onView={onView} />)

      fireEvent.click(screen.getByText('查看'))

      expect(onView).toHaveBeenCalledTimes(1)
      expect(onView).toHaveBeenCalledWith('test-inspiration-1')
    })

    it('calls onCopy when use button is clicked', () => {
      const onCopy = vi.fn()
      render(<InspirationCard inspiration={mockInspiration} onCopy={onCopy} />)

      fireEvent.click(screen.getByText('使用'))

      expect(onCopy).toHaveBeenCalledTimes(1)
      expect(onCopy).toHaveBeenCalledWith('test-inspiration-1')
    })
  })

  describe('Copying State', () => {
    it('shows copying text when isCopying is true', () => {
      render(<InspirationCard inspiration={mockInspiration} isCopying={true} />)

      expect(screen.getByText('复制中...')).toBeInTheDocument()
    })

    it('disables use button when copying', () => {
      render(<InspirationCard inspiration={mockInspiration} isCopying={true} />)

      const button = screen.getByText('复制中...').closest('button')
      expect(button).toBeDisabled()
    })

    it('shows use text when not copying', () => {
      render(<InspirationCard inspiration={mockInspiration} isCopying={false} />)

      expect(screen.getByText('使用')).toBeInTheDocument()
    })

    it('does not call onCopy when button is disabled', () => {
      const onCopy = vi.fn()
      render(<InspirationCard inspiration={mockInspiration} onCopy={onCopy} isCopying={true} />)

      const button = screen.getByText('复制中...').closest('button') as HTMLButtonElement
      fireEvent.click(button)

      // Button is disabled, so click should not trigger the handler
      expect(onCopy).not.toHaveBeenCalled()
    })
  })

  describe('Project Type Labels', () => {
    it('shows novel label for novel type', () => {
      const inspiration = { ...mockInspiration, project_type: 'novel' as const }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('长篇小说')).toBeInTheDocument()
    })

    it('shows short label for short type', () => {
      const inspiration = { ...mockInspiration, project_type: 'short' as const }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('短篇小说')).toBeInTheDocument()
    })

    it('shows screenplay label for screenplay type', () => {
      const inspiration = { ...mockInspiration, project_type: 'screenplay' as const }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('剧本')).toBeInTheDocument()
    })

    it('shows raw project type for unknown type', () => {
      const inspiration = { ...mockInspiration, project_type: 'unknown' as 'novel' }
      render(<InspirationCard inspiration={inspiration} />)

      expect(screen.getByText('unknown')).toBeInTheDocument()
    })
  })

  describe('Optional Callbacks', () => {
    it('works without onView callback', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      // Should not throw when clicking without callback
      fireEvent.click(screen.getByText('Test Inspiration'))
      fireEvent.click(screen.getByText('查看'))
    })

    it('works without onCopy callback', () => {
      render(<InspirationCard inspiration={mockInspiration} />)

      // Should not throw when clicking without callback
      fireEvent.click(screen.getByText('使用'))
    })
  })
})
