import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BottomTabs } from '../BottomTabs'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          'editor:bottomTabs.files': 'Files',
          'editor:bottomTabs.editor': 'Editor',
          'editor:bottomTabs.ai': 'AI Chat',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

describe('BottomTabs', () => {
  it('renders all tabs and marks the active one', () => {
    render(<BottomTabs activeTab="editor" onTabChange={vi.fn()} />)

    expect(screen.getByRole('tablist', { name: 'Mobile navigation' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Files' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tab', { name: 'Editor' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'AI Chat' })).toHaveAttribute('aria-selected', 'false')
  })

  it('notifies when a different tab is selected', () => {
    const onTabChange = vi.fn()
    render(<BottomTabs activeTab="files" onTabChange={onTabChange} />)

    fireEvent.click(screen.getByRole('tab', { name: 'AI Chat' }))

    expect(onTabChange).toHaveBeenCalledWith('chat')
  })
})
