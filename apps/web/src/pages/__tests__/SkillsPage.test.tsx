/**
 * SkillsPage Unit Tests
 *
 * These tests verify that the SkillsPage component mounts correctly
 * and that all useEffect hooks reference functions that are defined
 * before they are used (temporal dead zone prevention).
 *
 * IMPORTANT: This catches issues like the "Cannot access 'w' before initialization"
 * error that only manifests in production builds with minification.
 *
 * Background: A production bug was found where useEffect dependency arrays
 * referenced functions that were defined later in the component. In development
 * mode, JavaScript's hoisting behavior masked this issue, but minification
 * in production exposed the temporal dead zone error.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SkillsPage from '../SkillsPage'
import { ApiError } from '../../lib/apiClient'
import type { Skill, AddedSkill, PublicSkill, SkillCategory, MySkillsResponse, PublicSkillListResponse } from '../../types'

// Mock dependencies
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'title': 'Skills',
        'description': 'Manage your AI assistant skills',
        'discoverTab': 'Discover',
        'mySkillsTab': 'My Skills',
        'create': 'Create',
        'searchPlaceholder': 'Search skills...',
        'searchMySkillsPlaceholder': 'Search my skills...',
        'allCategories': 'All',
        'noSkillsFound': 'No skills found',
        'addToMine': 'Add',
        'alreadyAdded': 'Added',
        'addCount': 'users',
        'expand': 'Expand',
        'collapse': 'Collapse',
        'userSkills': 'My Skills',
        'addedSkills': 'Added Skills',
        'noUserSkills': 'No skills yet',
        'noAddedSkills': 'No added skills',
        'createFirst': 'Create your first skill',
        'discoverMore': 'Discover more',
        'browsePublic': 'Browse public skills',
        'noSearchResults': 'No results found',
        'skills:readonly': 'Read-only',
        'skills:added': 'Added',
        'skills:share.title': 'Share',
        'skills:remove': 'Remove',
        'skills:editSkill': 'Edit Skill',
        'skills:createSkill': 'Create Skill',
        'skills:deleteConfirm.title': 'Delete Skill',
        'skills:deleteConfirm.message': 'Are you sure you want to delete this skill?',
        'skills:batch.deleteConfirmTitle': 'Delete Skills',
        'skills:batch.deleteConfirmMessage': `Delete ${1} skills?`,
        'skills:batch.selectAll': 'Select All',
        'skills:batch.selected': `${1} selected`,
        'skills:batch.clearSelection': 'Clear',
        'skills:batch.delete': 'Delete',
        'skills:form.name': 'Name',
        'skills:form.namePlaceholder': 'Skill name',
        'skills:form.description': 'Description',
        'skills:form.descriptionPlaceholder': 'Brief description',
        'skills:form.triggers': 'Triggers',
        'skills:form.triggersPlaceholder': 'trigger1, trigger2',
        'skills:form.triggersHint': 'Comma-separated keywords',
        'skills:form.instructions': 'Instructions',
        'skills:form.instructionsPlaceholder': 'Detailed instructions',
        'skills:form.instructionsHint': 'Markdown supported',
        'skills:collapse': 'Collapse',
        'skills:expand': 'Expand',
        'skills:official': 'Official',
        'stats.title': 'Statistics',
        'common:cancel': 'Cancel',
        'common:save': 'Save',
        'common:delete': 'Delete',
      }
      return translations[key] || key
    },
    i18n: {
      changeLanguage: vi.fn(),
    },
  }),
}))

vi.mock('../../hooks/useMediaQuery', () => ({
  useIsMobile: () => false,
  useIsTablet: () => false,
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    currentProject: { id: 'project-1', name: 'Test Project' },
    currentProjectId: 'project-1',
  }),
}))

vi.mock('../../lib/api', () => ({
  skillsApi: {
    mySkills: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    batchUpdate: vi.fn(),
  },
  publicSkillsApi: {
    list: vi.fn(),
    getCategories: vi.fn(),
    add: vi.fn(),
    remove: vi.fn(),
  },
}))

// Mock react-markdown to avoid complexity
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}))

// Mock dialog components
vi.mock('../../components/SkillStatsDialog', () => ({
  SkillStatsDialog: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="stats-dialog">Stats Dialog</div> : null,
}))

vi.mock('../../components/skills/ShareSkillModal', () => ({
  ShareSkillModal: ({ skill }: { skill: Skill | null }) =>
    skill ? <div data-testid="share-modal">Share: {skill.name}</div> : null,
}))

vi.mock('../../components/subscription/UpgradePromptModal', () => ({
  UpgradePromptModal: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="upgrade-modal">{title}</div> : null,
}))

// Suppress console noise
vi.spyOn(console, 'error').mockImplementation(() => {})
vi.spyOn(console, 'log').mockImplementation(() => {})

import { skillsApi, publicSkillsApi } from '../../lib/api'

// Test data fixtures
const mockUserSkills: Skill[] = [
  {
    id: 'skill-1',
    name: 'Writing Assistant',
    description: 'Helps with creative writing',
    triggers: ['write', 'help'],
    instructions: 'You are a writing assistant.',
    source: 'user',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 'skill-2',
    name: 'Character Builder',
    description: 'Creates character profiles',
    triggers: ['character', 'profile'],
    instructions: 'Help create detailed character profiles.',
    source: 'user',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-03T00:00:00Z',
  },
]

const mockAddedSkills: AddedSkill[] = [
  {
    id: 'added-1',
    public_skill_id: 'public-1',
    name: 'Plot Twist Generator',
    description: 'Generates plot twists',
    instructions: 'Generate unexpected plot twists.',
    category: 'Writing',
    source: 'added',
    is_active: true,
    added_at: '2024-01-01T00:00:00Z',
  },
]

const mockPublicSkills: PublicSkill[] = [
  {
    id: 'public-1',
    name: 'Dialogue Expert',
    description: 'Expert at writing dialogue',
    instructions: 'Write natural dialogue.',
    category: 'Writing',
    tags: ['dialogue'],
    source: 'official',
    author_id: null,
    status: 'approved',
    add_count: 100,
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'public-2',
    name: 'World Builder',
    description: 'Builds immersive worlds',
    instructions: 'Create detailed world settings.',
    category: 'Worldbuilding',
    tags: ['world'],
    source: 'community',
    author_id: 'user-1',
    author_name: 'Community User',
    status: 'approved',
    add_count: 50,
    created_at: '2024-01-01T00:00:00Z',
  },
]

const mockCategories: SkillCategory[] = [
  { name: 'Writing', count: 10 },
  { name: 'Worldbuilding', count: 5 },
  { name: 'Characters', count: 8 },
]

describe('SkillsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Set up default mock implementations
    vi.mocked(publicSkillsApi.list).mockImplementation(async () => ({
      skills: mockPublicSkills,
      total: 2,
      page: 1,
      page_size: 20,
    } as PublicSkillListResponse))

    vi.mocked(publicSkillsApi.getCategories).mockImplementation(async () => ({
      categories: mockCategories,
    }))

    vi.mocked(skillsApi.mySkills).mockImplementation(async () => ({
      user_skills: mockUserSkills,
      added_skills: mockAddedSkills,
      total: 3,
    } as MySkillsResponse))
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // ========================================
  // 1. Component Mount Tests (TDZ Prevention)
  // ========================================
  describe('Component Mount (Temporal Dead Zone Prevention)', () => {
    it('should mount without throwing initialization errors', async () => {
      // This test verifies that all functions used in useEffect hooks
      // are defined BEFORE the useEffect hooks that reference them.
      // In development mode, hoisting masks temporal dead zone issues.
      // In production minification, these errors are exposed.
      render(<SkillsPage />)

      // Wait for the component to finish rendering
      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // Verify loadDiscoverData was called on mount (discover is default tab)
      expect(publicSkillsApi.list).toHaveBeenCalled()
      expect(publicSkillsApi.getCategories).toHaveBeenCalled()
    })

    it('should not throw when useEffect callbacks reference useCallback functions', async () => {
      // This specifically tests the pattern where useEffect depends on
      // functions wrapped in useCallback - those functions must be defined
      // before the useEffect hook
      const { unmount } = render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // Unmounting should also not throw
      expect(() => unmount()).not.toThrow()
    })
  })

  // ========================================
  // 2. Initial Load Tests
  // ========================================
  describe('Initial Load', () => {
    it('should load discover data on mount', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(publicSkillsApi.list).toHaveBeenCalled()
        expect(publicSkillsApi.getCategories).toHaveBeenCalled()
      })
    })

    it('should display discover tab by default', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Discover')).toBeInTheDocument()
        // The discover tab should be active (has gradient styling)
        const discoverButton = screen.getByRole('button', { name: /discover/i })
        expect(discoverButton).toBeInTheDocument()
      })
    })

    it('should show loading state initially', async () => {
      // Delay the API response
      vi.mocked(publicSkillsApi.list).mockImplementation(() =>
        new Promise(resolve => setTimeout(() => resolve({
          skills: [],
          total: 0,
          page: 1,
          page_size: 20,
        } as PublicSkillListResponse), 100))
      )

      render(<SkillsPage />)

      // Should show loading spinner
      expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    })
  })

  // ========================================
  // 3. Tab Switching Tests
  // ========================================
  describe('Tab Switching', () => {
    it('should switch between tabs correctly', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // Click on "My Skills" tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      // Should load my skills data
      await waitFor(() => {
        expect(skillsApi.mySkills).toHaveBeenCalled()
      })
    })

    it('should load my skills only when tab becomes active', async () => {
      render(<SkillsPage />)

      // Discover tab is active by default, mySkills should not be called yet
      await waitFor(() => {
        expect(publicSkillsApi.list).toHaveBeenCalled()
      })

      // Clear the mock to track new calls
      vi.mocked(skillsApi.mySkills).mockClear()

      // Switch to my skills tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      // Now mySkills should be called
      await waitFor(() => {
        expect(skillsApi.mySkills).toHaveBeenCalled()
      })
    })
  })

  // =================================-------
  // 4. Discover Tab Tests
  // ========================================
  describe('Discover Tab', () => {
    it('should display public skills', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Dialogue Expert')).toBeInTheDocument()
        expect(screen.getByText('World Builder')).toBeInTheDocument()
      })
    })

    it('should display categories', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Writing')).toBeInTheDocument()
        expect(screen.getByText('Worldbuilding')).toBeInTheDocument()
      })
    })

    it('should filter by category', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // Click on a category
      const writingCategory = screen.getByRole('button', { name: 'Writing' })
      await userEvent.click(writingCategory)

      // API should be called with category filter
      await waitFor(() => {
        expect(publicSkillsApi.list).toHaveBeenCalledWith(
          expect.objectContaining({ category: 'Writing' })
        )
      })
    })

    it('should search skills', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText('Search skills...')
      await userEvent.type(searchInput, 'dialogue')

      // Wait for debounce and API call
      await waitFor(() => {
        expect(publicSkillsApi.list).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'dialogue' })
        )
      }, { timeout: 1000 })
    })

    it('should add public skill to my skills', async () => {
      vi.mocked(publicSkillsApi.add).mockResolvedValue(undefined)

      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Dialogue Expert')).toBeInTheDocument()
      })

      // Find and click the add button
      const addButtons = screen.getAllByRole('button', { name: /add$/i })
      await userEvent.click(addButtons[0])

      await waitFor(() => {
        expect(publicSkillsApi.add).toHaveBeenCalled()
      })
    })
  })

  // ========================================
  // 5. My Skills Tab Tests
  // ========================================
  describe('My Skills Tab', () => {
    it('should display user skills', async () => {
      render(<SkillsPage />)

      // Switch to my skills tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Writing Assistant')).toBeInTheDocument()
        expect(screen.getByText('Character Builder')).toBeInTheDocument()
      })
    })

    it('should display added skills', async () => {
      render(<SkillsPage />)

      // Switch to my skills tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Plot Twist Generator')).toBeInTheDocument()
      })
    })

    it('should open create skill modal', async () => {
      render(<SkillsPage />)

      // Switch to my skills tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Writing Assistant')).toBeInTheDocument()
      })

      // Click create button
      const createButton = screen.getByRole('button', { name: /create$/i })
      await userEvent.click(createButton)

      // Modal should appear
      await waitFor(() => {
        expect(screen.getByText('Create Skill')).toBeInTheDocument()
      })
    })

    it('should keep typing focus inside create skill modal inputs', async () => {
      render(<SkillsPage />)

      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Writing Assistant')).toBeInTheDocument()
      })

      const createButton = screen.getByRole('button', { name: /create$/i })
      await userEvent.click(createButton)

      await waitFor(() => {
        expect(screen.getByText('Create Skill')).toBeInTheDocument()
      })

      const nameInput = screen.getByPlaceholderText('Skill name')
      await userEvent.type(nameInput, 'Skill 123')

      expect(nameInput).toHaveValue('Skill 123')
      expect(nameInput).toHaveFocus()
    })

    it('should search my skills', async () => {
      render(<SkillsPage />)

      // Switch to my skills tab
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      vi.mocked(skillsApi.mySkills).mockClear()

      const searchInput = screen.getByPlaceholderText('Search my skills...')
      await userEvent.type(searchInput, 'writing')

      // Wait for debounce and API call
      await waitFor(() => {
        expect(skillsApi.mySkills).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'writing' })
        )
      }, { timeout: 1000 })
    })

    it('shows upgrade modal when creating skill hits quota limit', async () => {
      vi.mocked(skillsApi.create).mockRejectedValueOnce(new ApiError(402, 'ERR_QUOTA_EXCEEDED'))

      render(<SkillsPage />)

      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      await waitFor(() => {
        expect(screen.getByText('Writing Assistant')).toBeInTheDocument()
      })

      const createButton = screen.getByRole('button', { name: /create$/i })
      await userEvent.click(createButton)

      await waitFor(() => {
        expect(screen.getByText('Create Skill')).toBeInTheDocument()
      })

      await userEvent.type(screen.getByPlaceholderText('Skill name'), 'Quota Skill')
      await userEvent.type(screen.getByPlaceholderText('Detailed instructions'), 'do something')
      await userEvent.click(screen.getByRole('button', { name: /save/i }))

      await waitFor(() => {
        expect(skillsApi.create).toHaveBeenCalled()
        expect(screen.getByTestId('upgrade-modal')).toBeInTheDocument()
      })
    })
  })

  // ========================================
  // 6. Error Handling Tests
  // ========================================
  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      vi.mocked(publicSkillsApi.list).mockRejectedValue(new Error('Network error'))

      render(<SkillsPage />)

      // Component should still render without crashing
      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })
    })

    it('should handle empty skills list', async () => {
      vi.mocked(publicSkillsApi.list).mockResolvedValue({
        skills: [],
        total: 0,
        page: 1,
        page_size: 20,
      } as PublicSkillListResponse)

      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('No skills found')).toBeInTheDocument()
      })
    })
  })

  // ========================================
  // 7. useCallback Function Order Tests
  // ========================================
  describe('useCallback Function Order', () => {
    it('should have loadDiscoverData defined before useEffect that uses it', async () => {
      // This is a structural test - if loadDiscoverData was defined after
      // the useEffect that depends on it, this test would fail in minified builds
      render(<SkillsPage />)

      // The component should mount successfully
      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // And the function should have been called
      expect(publicSkillsApi.list).toHaveBeenCalled()
    })

    it('should have loadSkills defined before useEffect that uses it', async () => {
      render(<SkillsPage />)

      // Switch to my-skills tab which triggers the loadSkills useEffect
      const mySkillsTab = screen.getByRole('button', { name: /my skills/i })
      await userEvent.click(mySkillsTab)

      // Should load without errors
      await waitFor(() => {
        expect(skillsApi.mySkills).toHaveBeenCalled()
      })
    })

    it('should have loadPublicSkills defined before useEffect that uses it', async () => {
      render(<SkillsPage />)

      await waitFor(() => {
        expect(screen.getByText('Skills')).toBeInTheDocument()
      })

      // Change search query which triggers loadPublicSkills
      const searchInput = screen.getByPlaceholderText('Search skills...')
      await userEvent.type(searchInput, 'test')

      // Should not throw TDZ error
      await waitFor(() => {
        expect(publicSkillsApi.list).toHaveBeenCalled()
      })
    })
  })
})
