import { subscriptionApi } from '@/lib/subscriptionApi'
import useSubscriptionStore from '../subscriptionStore'

vi.mock('@/lib/subscriptionApi', () => ({
  subscriptionApi: {
    getStatus: vi.fn(),
    getQuota: vi.fn(),
  },
}))

const initialState = useSubscriptionStore.getState()

describe('subscriptionStore', () => {
  beforeEach(() => {
    useSubscriptionStore.setState(initialState, true)
    vi.clearAllMocks()
  })

  it('fetches subscription status successfully', async () => {
    vi.mocked(subscriptionApi.getStatus).mockResolvedValue({
      tier: 'pro',
      is_active: true,
      expires_at: null,
    } as never)

    await useSubscriptionStore.getState().fetchSubscription()

    expect(subscriptionApi.getStatus).toHaveBeenCalled()
    expect(useSubscriptionStore.getState().subscription?.tier).toBe('pro')
    expect(useSubscriptionStore.getState().isLoading).toBe(false)
    expect(useSubscriptionStore.getState().error).toBe(null)
  })

  it('stores a readable error when fetching quota fails', async () => {
    vi.mocked(subscriptionApi.getQuota).mockRejectedValue(new Error('quota failed'))

    await useSubscriptionStore.getState().fetchQuota()

    expect(useSubscriptionStore.getState().quota).toBe(null)
    expect(useSubscriptionStore.getState().error).toBe('quota failed')
    expect(useSubscriptionStore.getState().isLoading).toBe(false)
  })

  it('refreshes subscription and quota in parallel', async () => {
    vi.mocked(subscriptionApi.getStatus).mockResolvedValue({
      tier: 'free',
      is_active: false,
      expires_at: null,
    } as never)
    vi.mocked(subscriptionApi.getQuota).mockResolvedValue({
      ai_conversations: {
        used: 2,
        limit: 10,
      },
    } as never)

    await useSubscriptionStore.getState().refresh()

    expect(subscriptionApi.getStatus).toHaveBeenCalled()
    expect(subscriptionApi.getQuota).toHaveBeenCalled()
    expect(useSubscriptionStore.getState().getTier()).toBe('free')
    expect(useSubscriptionStore.getState().getAiConversationsRemaining()).toBe(8)
    expect(useSubscriptionStore.getState().isPro()).toBe(false)
  })

  it('treats unlimited quotas and pro tiers correctly', () => {
    useSubscriptionStore.setState({
      ...useSubscriptionStore.getState(),
      subscription: {
        tier: 'pro',
        is_active: true,
        expires_at: null,
      } as never,
      quota: {
        ai_conversations: {
          used: 999,
          limit: -1,
        },
      } as never,
    })

    expect(useSubscriptionStore.getState().isPro()).toBe(true)
    expect(useSubscriptionStore.getState().getTier()).toBe('pro')
    expect(useSubscriptionStore.getState().getAiConversationsRemaining()).toBe(null)
  })
})
