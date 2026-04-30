import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { ApiError } from '../../lib/apiClient'

let mockLanguage = 'zh-CN'
let mockIsMobile = false
let mockIsTablet = false
let mockProjects: Array<{ id: string; name: string; project_type: 'novel'; updated_at?: string | null }> = []
let mockProjectsLoading = false
let mockFeaturedState: {
  featured: Array<{ id: string; name: string; description?: string; project_type: 'novel' }>;
  isLoading: boolean;
  isFetching: boolean;
} = {
  featured: [],
  isLoading: false,
  isFetching: false,
}
let mockActivationGuide: {
  user_id: string;
  window_hours: number;
  within_first_day: boolean;
  total_steps: number;
  completed_steps: number;
  completion_rate: number;
  is_activated: boolean;
  next_event_name: string | null;
  next_action: string | null;
  steps: Array<{
    event_name: string;
    label: string;
    completed: boolean;
    completed_at: string | null;
    action_path: string;
  }>;
} | null = null
let mockPersonaRecommendations: Array<{
  id: string;
  title: string;
  description: string;
  action: string;
}> = []
let mockDashboardInspirations: Array<{
  id: string;
  title: string;
  hook: string;
  tags: string[];
  source: string;
}> = []

const {
  mockDashboardOnboardingFlags,
  mockGetActivationGuide,
  mockGetRecommendations,
} = vi.hoisted(() => ({
  mockDashboardOnboardingFlags: {
    todayActionPlanEnabled: true,
    firstDayActivationGuideEnabled: true,
  },
  mockGetActivationGuide: vi.fn(),
  mockGetRecommendations: vi.fn(),
}))

const mockNavigate = vi.fn()
const mockCreateProject = vi.fn()
const mockDeleteProject = vi.fn()

const mockT = (
  key: string,
  options?: { defaultValue?: string; name?: string } | string,
) => {
  const optionObj = typeof options === 'string' ? undefined : options
  const translations: Record<string, string> = {
    'hero.greeting': `你好 ${optionObj?.name ?? '创作者'}`,
    'hero.question': '今天想创作些什么呢？',
    'inspirations.featured': '精选灵感',
    'projects.viewAll': '浏览全部',
    'projects.recent': '最近项目',
    'projects.empty': '还没有任何项目',
    'projects.emptyHint': '在上方输入灵感，点击「开始创作」创建你的第一个项目',
    'common.createButton': '开始创作',
    'projectType.novel.name': '长篇小说',
    'inspiration.novelDesc': 'AI 将根据你的灵感，帮你构思故事框架、设定世界观和人物角色',
    'inspiration.novelPlaceholder': '请输入灵感',
    'activationGuide.steps.signup_success': '完成注册',
    'activationGuide.steps.project_created': '创建项目',
    'activationGuide.steps.first_file_saved': '保存首个文件',
    'activationGuide.steps.first_ai_action_accepted': '接受首个 AI 动作',
  }
  if (typeof options === 'string') {
    return translations[key] || options || key
  }
  return translations[key] || options?.defaultValue || key
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: mockT,
    i18n: {
      get language() {
        return mockLanguage
      },
      get resolvedLanguage() {
        return mockLanguage
      },
    },
  }),
}))

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      username: 'tester',
      nickname: null,
      email: 'tester@example.com',
    },
  }),
}))

vi.mock('../../contexts/ProjectContext', () => ({
  useProject: () => ({
    projects: mockProjects,
    loading: mockProjectsLoading,
    createProject: mockCreateProject,
    deleteProject: mockDeleteProject,
  }),
}))

vi.mock('../../hooks/useInspirations', () => ({
  useFeaturedInspirations: () => mockFeaturedState,
}))

vi.mock('../../hooks/useMediaQuery', () => ({
  useIsMobile: () => mockIsMobile,
  useIsTablet: () => mockIsTablet,
}))

vi.mock('../../hooks/useDashboardInspirations', () => ({
  useDashboardInspirations: () => mockDashboardInspirations,
}))

vi.mock('../../components/subscription/UpgradePromptModal', () => ({
  UpgradePromptModal: ({ open, title }: { open: boolean; title: string }) =>
    open ? <div data-testid="upgrade-modal">{title}</div> : null,
}))

vi.mock('../../lib/api', () => ({
  projectApi: {
    getTemplates: vi.fn().mockResolvedValue(null),
  },
}))

vi.mock('../../lib/writingStatsApi', () => ({
  writingStatsApi: {
    getActivationGuide: mockGetActivationGuide,
  },
}))

vi.mock('../../lib/onboardingPersonaApi', () => ({
  onboardingPersonaApi: {
    getRecommendations: mockGetRecommendations,
  },
}))

vi.mock('../../config/dashboardOnboarding', () => ({
  dashboardOnboardingFlags: mockDashboardOnboardingFlags,
}))

import DashboardHome from '../DashboardHome'

const renderDashboardHome = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardHome />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardHome featured inspirations section', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateProject.mockResolvedValue({ id: 'project-created' })
    mockLanguage = 'zh-CN'
    mockIsMobile = false
    mockIsTablet = false
    mockProjects = []
    mockProjectsLoading = false
    mockFeaturedState = {
      featured: [],
      isLoading: false,
      isFetching: false,
    }
    mockActivationGuide = null
    mockPersonaRecommendations = []
    mockDashboardOnboardingFlags.todayActionPlanEnabled = true
    mockDashboardOnboardingFlags.firstDayActivationGuideEnabled = true
    mockDashboardInspirations = []
    mockGetActivationGuide.mockImplementation(() => Promise.resolve(mockActivationGuide))
    mockGetRecommendations.mockImplementation(() => Promise.resolve(mockPersonaRecommendations))
  })

  it('always shows featured section and renders empty CTA when featured list is empty', () => {
    renderDashboardHome()

    expect(screen.getByTestId('featured-inspirations-section')).toBeInTheDocument()
    expect(screen.getByText('暂无精选灵感')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '查看灵感库' }))
    expect(mockNavigate).toHaveBeenCalledWith('/dashboard/inspirations')
  })

  it('renders real inspiration cards and fills the input when clicked', () => {
    mockDashboardInspirations = [
      {
        id: 'qimao:1983473',
        title: '狂兽战神',
        hook: '被皇朝与挚爱联手陷害的神将，流放后反掌万兽',
        tags: ['玄幻奇幻', '东方玄幻'],
        source: 'qimao_detail',
      },
    ]

    renderDashboardHome()

    expect(screen.getByTestId('dashboard-real-inspirations')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /狂兽战神/i }))

    expect(screen.getByTestId('dashboard-inspiration-input')).toHaveValue(
      '《狂兽战神》：被皇朝与挚爱联手陷害的神将，流放后反掌万兽',
    )
  })

  it('keeps existing featured cards when featured inspirations are available', () => {
    mockFeaturedState = {
      featured: [
        {
          id: 'insp-1',
          name: '赛博修仙都市',
          description: '未来都市与修仙体系结合',
          project_type: 'novel',
        },
      ],
      isLoading: false,
      isFetching: false,
    }

    renderDashboardHome()

    expect(screen.getByText('赛博修仙都市')).toBeInTheDocument()
    expect(screen.queryByText('暂无精选灵感')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('赛博修仙都市'))
    expect(mockNavigate).toHaveBeenCalledWith('/dashboard/inspirations/insp-1')
  })

  it('shows loading skeleton while featured inspirations are loading', () => {
    mockFeaturedState = {
      featured: [],
      isLoading: true,
      isFetching: true,
    }

    renderDashboardHome()

    expect(screen.getByTestId('featured-inspirations-loading')).toBeInTheDocument()
  })

  it('shows activation guide card for first-day users and next action is actionable', async () => {
    mockActivationGuide = {
      user_id: 'u-1',
      window_hours: 24,
      within_first_day: true,
      total_steps: 4,
      completed_steps: 2,
      completion_rate: 0.5,
      is_activated: false,
      next_event_name: 'first_file_saved',
      next_action: '/dashboard',
      steps: [
        {
          event_name: 'signup_success',
          label: 'Signup Success',
          completed: true,
          completed_at: '2026-03-08T00:00:00Z',
          action_path: '/dashboard',
        },
        {
          event_name: 'project_created',
          label: 'Project Created',
          completed: true,
          completed_at: '2026-03-08T00:01:00Z',
          action_path: '/dashboard',
        },
        {
          event_name: 'first_file_saved',
          label: 'First File Saved',
          completed: false,
          completed_at: null,
          action_path: '/dashboard',
        },
        {
          event_name: 'first_ai_action_accepted',
          label: 'First AI Action Accepted',
          completed: false,
          completed_at: null,
          action_path: '/dashboard',
        },
      ],
    }

    mockProjects = [
      { id: 'project-1', name: '最近项目', project_type: 'novel', updated_at: '2026-03-08T00:02:00Z' },
    ]

    renderDashboardHome()

    expect(await screen.findByTestId('featured-inspirations-section')).toBeInTheDocument()
    const guideCard = await screen.findByTestId('activation-guide-card')
    const guide = within(guideCard)
    expect(guideCard).toBeInTheDocument()
    expect(guide.getByText('首日激活向导')).toBeInTheDocument()

    // Language adaptation: show localized step labels instead of raw backend English.
    expect(guide.getByText('完成注册')).toBeInTheDocument()
    expect(guide.getByText('创建项目')).toBeInTheDocument()
    expect(guide.getByText('保存首个文件')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '继续下一步' }))
    expect(mockNavigate).toHaveBeenCalledWith('/project/project-1')
  })

  it('shows today action plan entry and executes activation action', async () => {
    // Preference A: if activation guide is shown, today-action-plan is hidden.
    // Use a non-first-day (or no activation guide) scenario to validate the action plan.
    mockActivationGuide = null
    mockProjects = []
    mockPersonaRecommendations = []

    renderDashboardHome()

    const todayActionCard = await screen.findByTestId('today-action-plan-card')
    const todayAction = within(todayActionCard)
    expect(todayActionCard).toBeInTheDocument()
    expect(await todayAction.findByText('创建你的首个项目')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('today-action-execute-1'))

    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalled()
      expect(mockNavigate).toHaveBeenCalledWith('/project/project-created')
    })
  })

  it('does not flash today action plan while projects are still loading', async () => {
    mockActivationGuide = null
    mockPersonaRecommendations = []
    mockProjects = []
    mockProjectsLoading = true

    renderDashboardHome()

    await waitFor(() => {
      expect(screen.queryByTestId('today-action-plan-card')).not.toBeInTheDocument()
    })
  })

  it('hides today action plan for returning users who already have projects', () => {
    mockActivationGuide = null
    mockPersonaRecommendations = []
    mockProjectsLoading = false
    mockProjects = [
      { id: 'project-1', name: '已有项目', project_type: 'novel', updated_at: '2026-03-08T00:02:00Z' },
    ]

    renderDashboardHome()

    expect(screen.queryByTestId('today-action-plan-card')).not.toBeInTheDocument()
  })

  it('keeps onboarding panels hidden when dashboard onboarding flags are off', async () => {
    mockDashboardOnboardingFlags.todayActionPlanEnabled = false
    mockDashboardOnboardingFlags.firstDayActivationGuideEnabled = false
    mockActivationGuide = {
      user_id: 'u-1',
      window_hours: 24,
      within_first_day: true,
      total_steps: 4,
      completed_steps: 1,
      completion_rate: 0.25,
      is_activated: false,
      next_event_name: 'project_created',
      next_action: '/dashboard',
      steps: [
        {
          event_name: 'signup_success',
          label: 'Signup Success',
          completed: true,
          completed_at: '2026-03-08T00:00:00Z',
          action_path: '/dashboard',
        },
        {
          event_name: 'project_created',
          label: 'Project Created',
          completed: false,
          completed_at: null,
          action_path: '/dashboard',
        },
      ],
    }
    mockPersonaRecommendations = [
      {
        id: 'level_beginner_path',
        title: '新手先看灵感',
        description: '先熟悉灵感广场，再开始创作。',
        action: '/dashboard',
      },
    ]

    renderDashboardHome()

    await waitFor(() => {
      expect(screen.queryByTestId('activation-guide-card')).not.toBeInTheDocument()
      expect(screen.queryByTestId('today-action-plan-card')).not.toBeInTheDocument()
    })
    expect(mockGetActivationGuide).not.toHaveBeenCalled()
    expect(mockGetRecommendations).not.toHaveBeenCalled()
  })

  it('shows project quota upgrade modal when quick create hits limit', async () => {
    mockCreateProject.mockRejectedValueOnce(new ApiError(402, 'ERR_QUOTA_PROJECTS_EXCEEDED'))

    renderDashboardHome()

    fireEvent.change(screen.getByTestId('dashboard-inspiration-input'), {
      target: { value: '灵感测试' },
    })
    fireEvent.click(screen.getByTestId('create-project-button'))

    expect(await screen.findByTestId('upgrade-modal')).toBeInTheDocument()
  })
})
