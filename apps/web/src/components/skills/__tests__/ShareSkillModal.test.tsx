import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ShareSkillModal } from '../ShareSkillModal'

const mockShare = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          'skills:share.title': 'Share skill',
          'skills:share.category': 'Category',
          'skills:share.notice': 'Sharing publishes the skill',
          'skills:share.error': 'Share failed',
          'skills:share.submit': 'Share now',
          'common:cancel': 'Cancel',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

vi.mock('../../ui/Modal', () => ({
  default: ({
    open,
    title,
    footer,
    children,
  }: {
    open: boolean
    title: React.ReactNode
    footer: React.ReactNode
    children?: React.ReactNode
  }) => (open ? <div><div>{title}</div>{children}{footer}</div> : null),
}))

vi.mock('../../../lib/api', () => ({
  skillsApi: {
    share: (...args: unknown[]) => mockShare(...args),
  },
}))

describe('ShareSkillModal', () => {
  const skill = {
    id: 'skill-1',
    name: 'Dialogue Helper',
    description: 'Improves dialogue',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockShare.mockResolvedValue({ success: true })
  })

  it('shares a skill successfully with the selected category', async () => {
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    render(<ShareSkillModal skill={skill as never} onClose={onClose} onSuccess={onSuccess} />)

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'plot' } })
    fireEvent.click(screen.getByRole('button', { name: 'Share now' }))

    await waitFor(() => {
      expect(mockShare).toHaveBeenCalledWith('skill-1', 'plot')
      expect(onSuccess).toHaveBeenCalled()
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('shows returned and fallback errors when sharing fails', async () => {
    mockShare
      .mockResolvedValueOnce({ success: false, message: 'Already shared' })
      .mockRejectedValueOnce(new Error('network down'))

    const { rerender } = render(
      <ShareSkillModal skill={skill as never} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Share now' }))
    expect(await screen.findByText('Already shared')).toBeInTheDocument()

    rerender(<ShareSkillModal skill={skill as never} onClose={vi.fn()} onSuccess={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Share now' }))
    expect(await screen.findByText('Share failed')).toBeInTheDocument()
  })
})
