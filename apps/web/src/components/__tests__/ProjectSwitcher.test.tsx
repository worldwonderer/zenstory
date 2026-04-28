import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectSwitcher } from '../ProjectSwitcher'

const mockNavigate = vi.fn()
const mockUseProject = vi.fn()
const toastErrorMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) =>
      (
        {
          'editor:projectSwitcher.loading': 'Loading projects',
          'editor:projectSwitcher.searchPlaceholder': 'Search projects',
          'editor:projectSwitcher.noResults': 'No results',
          'editor:projectSwitcher.noProjects': 'No projects',
          'editor:projectSwitcher.editName': 'Edit project',
          'editor:projectSwitcher.deleteProject': 'Delete project',
          'editor:projectSwitcher.projectNamePlaceholder': 'Project name',
          'editor:projectSwitcher.create': 'Create',
          'editor:projectSwitcher.createProject': 'Create project',
          'editor:projectSwitcher.confirmDelete': 'Delete it?',
          'editor:projectSwitcher.cannotDeleteLast': 'Cannot delete last project',
          'dashboard:billing.ctaUpgradePro': 'Upgrade',
          'home:pricingTeaser.viewPricing': 'View pricing',
        } as Record<string, string>
      )[key] ?? options?.defaultValue ?? key,
  }),
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => mockUseProject(),
}))

vi.mock('../../hooks/useMediaQuery', () => ({
  useIsMobile: () => false,
}))

vi.mock('../../lib/toast', () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
  },
}))

vi.mock('../../config/upgradeExperience', () => ({
  getUpgradePromptDefinition: () => ({
    source: 'project_quota_blocked',
    surface: 'modal',
    billingPath: '/billing',
    pricingPath: '/pricing',
  }),
  buildUpgradeUrl: (path: string) => `https://zenstory.local${path}`,
}))

vi.mock('../subscription/UpgradePromptModal', () => ({
  UpgradePromptModal: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="upgrade-modal">{title}</div> : null,
}))

describe('ProjectSwitcher', () => {
  const switchProject = vi.fn()
  const createProject = vi.fn()
  const updateProject = vi.fn()
  const deleteProject = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseProject.mockReturnValue({
      projects: [
        { id: 'project-1', name: 'Alpha', description: 'First project' },
        { id: 'project-2', name: 'Beta', description: 'Second project' },
      ],
      currentProject: { id: 'project-1', name: 'Alpha' },
      currentProjectId: 'project-1',
      loading: false,
      switchProject,
      createProject,
      updateProject,
      deleteProject,
    })
  })

  it('opens the dropdown, filters projects, and switches project', async () => {
    render(<ProjectSwitcher />)

    fireEvent.click(screen.getByRole('button', { name: /alpha/i }))
    expect(screen.getByPlaceholderText('Search projects')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Search projects'), {
      target: { value: 'Beta' },
    })
    expect(screen.getAllByText('Beta').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Beta'))
    expect(switchProject).toHaveBeenCalledWith('project-2')
    expect(mockNavigate).toHaveBeenCalledWith('/project/project-2')
  })

  it('renames a project inline and saves on Enter', async () => {
    updateProject.mockResolvedValue(undefined)

    render(<ProjectSwitcher />)
    fireEvent.click(screen.getByRole('button', { name: /alpha/i }))

    fireEvent.click(screen.getAllByTitle('Edit project')[0]!)
    const editInput = screen.getByDisplayValue('Alpha')
    fireEvent.change(editInput, { target: { value: 'Renamed project' } })
    fireEvent.keyDown(editInput, { key: 'Enter' })

    await waitFor(() => {
      expect(updateProject).toHaveBeenCalledWith('project-1', { name: 'Renamed project' })
    })
  })

  it('creates and deletes projects from the dropdown footer', async () => {
    createProject.mockResolvedValue({ id: 'project-3' })
    deleteProject.mockResolvedValue(undefined)

    vi.stubGlobal('confirm', vi.fn(() => true))

    render(<ProjectSwitcher />)
    fireEvent.click(screen.getByRole('button', { name: /alpha/i }))

    fireEvent.click(screen.getByRole('button', { name: 'Create project' }))
    fireEvent.change(screen.getByPlaceholderText('Project name'), {
      target: { value: 'Gamma' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(createProject).toHaveBeenCalledWith('Gamma')
      expect(mockNavigate).toHaveBeenCalledWith('/project/project-3')
    })

    fireEvent.click(screen.getByRole('button', { name: /alpha/i }))
    fireEvent.click(screen.getAllByTitle('Delete project')[1]!)
    await waitFor(() => {
      expect(deleteProject).toHaveBeenCalledWith('project-2')
    })
  })
})
