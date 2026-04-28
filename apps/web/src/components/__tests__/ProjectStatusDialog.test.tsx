import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'

const mockNavigate = vi.fn()
const mockProjectGet = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        title: 'AI 记忆',
        shareAsInspiration: '投稿到灵感库',
        sharingInspiration: '投稿中...',
        viewInspirationLibrary: '查看灵感库',
        cancel: '取消',
        save: '保存',
        saving: '保存中...',
        infoBanner: 'info',
        projectSummary: '项目简介',
        writingStyle: '写作风格',
        currentPhase: '当前阶段',
        notes: '备注',
        'placeholders.summary': 'summary placeholder',
        'placeholders.writingStyle': 'style placeholder',
        'placeholders.currentPhase': 'phase placeholder',
        'placeholders.notes': 'notes placeholder',
      }
      return translations[key] || key
    },
  }),
}))

vi.mock('../ui/Modal', () => {
  const Modal = ({
    open,
    title,
    children,
    footer,
  }: {
    open: boolean
    title?: ReactNode
    children: ReactNode
    footer?: ReactNode
  }) => {
    if (!open) return null
    return (
      <div>
        <div>{title}</div>
        <div>{children}</div>
        <div>{footer}</div>
      </div>
    )
  }

  return {
    Modal,
    default: Modal,
  }
})

vi.mock('../../lib/api', () => ({
  projectApi: {
    get: (...args: unknown[]) => mockProjectGet(...args),
    patch: vi.fn(),
  },
  inspirationsApi: {
    submit: vi.fn(),
  },
}))

vi.mock('../../lib/projectStatusEvents', () => ({
  subscribeProjectStatusUpdated: () => () => undefined,
}))

import { ProjectStatusDialog } from '../ProjectStatusDialog'

describe('ProjectStatusDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockProjectGet.mockResolvedValue({
      id: 'project-1',
      name: 'Test Project',
      description: 'desc',
      summary: '',
      writing_style: '',
      current_phase: '',
      notes: '',
    })
  })

  it('renders updated inspiration action labels', async () => {
    render(<ProjectStatusDialog isOpen={true} onClose={vi.fn()} projectId="project-1" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '投稿到灵感库' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '查看灵感库' })).toBeInTheDocument()
    })
  })

  it('navigates to inspiration library and closes dialog', async () => {
    const onClose = vi.fn()

    render(<ProjectStatusDialog isOpen={true} onClose={onClose} projectId="project-1" />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '查看灵感库' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '查看灵感库' }))

    expect(onClose).toHaveBeenCalledTimes(1)
    expect(mockNavigate).toHaveBeenCalledWith('/dashboard/inspirations')
  })
})
