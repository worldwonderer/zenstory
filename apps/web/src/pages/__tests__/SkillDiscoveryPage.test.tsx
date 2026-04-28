import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import SkillDiscoveryPage from '../SkillDiscoveryPage'

const mockList = vi.fn()
const mockGetCategories = vi.fn()
const mockAdd = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          'skills:discover': 'Discover Skills',
          'skills:discoverDescription': 'Browse public skills',
          'skills:searchPlaceholder': 'Search skills',
          'skills:allCategories': 'All',
          'skills:noSkillsFound': 'No skills found',
          'skills:addToMine': 'Add',
          'skills:alreadyAdded': 'Added',
          'skills:addCount': 'users',
          'skills:expand': 'Expand',
          'skills:collapse': 'Collapse',
          'skills:official': 'Official',
          'skills:community': 'Community',
          'skills:form.instructions': 'Instructions',
          'common:search': 'Search',
          'common:previous': 'Previous',
          'common:next': 'Next',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

vi.mock('../../hooks/useMediaQuery', () => ({
  useIsMobile: () => false,
  useIsTablet: () => false,
}))

vi.mock('../../components/LazyMarkdown', () => ({
  LazyMarkdown: ({ children }: { children: string }) => <div>{children}</div>,
}))

vi.mock('../../lib/api', () => ({
  publicSkillsApi: {
    list: (...args: unknown[]) => mockList(...args),
    getCategories: (...args: unknown[]) => mockGetCategories(...args),
    add: (...args: unknown[]) => mockAdd(...args),
  },
}))

const skillFixtures = [
  {
    id: 'skill-1',
    name: 'Dialogue Expert',
    description: 'Crafts natural dialogue',
    instructions: 'Use short, character-driven exchanges.',
    category: 'Writing',
    tags: ['dialogue', 'scene', 'voice'],
    source: 'official',
    author_name: null,
    add_count: 12,
    is_added: false,
  },
  {
    id: 'skill-2',
    name: 'World Builder',
    description: 'Builds settings',
    instructions: 'Develop cultures and environments.',
    category: 'Worldbuilding',
    tags: ['world'],
    source: 'community',
    author_name: 'Community User',
    add_count: 5,
    is_added: true,
  },
]

describe('SkillDiscoveryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCategories.mockResolvedValue({
      categories: [
        { name: 'Writing', count: 1 },
        { name: 'Worldbuilding', count: 1 },
      ],
    })
    mockList.mockResolvedValue({
      skills: skillFixtures,
      total: skillFixtures.length,
    })
    mockAdd.mockResolvedValue({ success: true })
  })

  const renderPage = () =>
    render(
      <MemoryRouter>
        <SkillDiscoveryPage />
      </MemoryRouter>,
    )

  it('loads categories and skills, expands instructions, and adds a skill', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Dialogue Expert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Writing (1)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Worldbuilding (1)' })).toBeInTheDocument()

    await user.click(screen.getAllByTitle('Expand')[0]!)
    expect(screen.getByText('Use short, character-driven exchanges.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => {
      expect(mockAdd).toHaveBeenCalledWith('skill-1')
      expect(screen.getAllByRole('button', { name: 'Added' }).length).toBeGreaterThan(0)
    })
  })

  it('filters by category and search query', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('Dialogue Expert')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Worldbuilding (1)' }))
    await waitFor(() => {
      expect(mockList).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: 'Worldbuilding' }),
      )
    })

    const searchInput = screen.getByPlaceholderText('Search skills')
    await user.clear(searchInput)
    await user.type(searchInput, 'dialogue')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => {
      expect(mockList).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'dialogue' }),
      )
    })
  })

  it('shows the empty state when no public skills are returned', async () => {
    mockList.mockResolvedValue({ skills: [], total: 0 })
    renderPage()

    expect(await screen.findByText('No skills found')).toBeInTheDocument()
  })
})
