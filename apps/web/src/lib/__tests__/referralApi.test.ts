import { describe, it, expect, vi, beforeEach } from 'vitest'
import { referralApi } from '../referralApi'
import * as apiClient from '../apiClient'

// Mock the apiClient but keep ApiError from the original
vi.mock('../apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof apiClient>()
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      patch: vi.fn(),
    },
  }
})

describe('referralApi', () => {
  const mockApiGet = vi.mocked(apiClient.api.get)
  const mockApiPost = vi.mocked(apiClient.api.post)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getInviteCodes', () => {
    it('calls correct endpoint', async () => {
      const mockCodes = [
        {
          id: 'code-1',
          code: 'ABCD-EFGH',
          max_uses: 10,
          current_uses: 3,
          is_active: true,
          expires_at: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]
      mockApiGet.mockResolvedValue(mockCodes)

      const result = await referralApi.getInviteCodes()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/referral/codes')
      expect(result).toEqual(mockCodes)
    })

    it('returns empty array when no codes', async () => {
      mockApiGet.mockResolvedValue([])

      const result = await referralApi.getInviteCodes()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/referral/codes')
      expect(result).toEqual([])
    })

    it('propagates errors from API', async () => {
      const error = new Error('Network error')
      mockApiGet.mockRejectedValue(error)

      await expect(referralApi.getInviteCodes()).rejects.toThrow('Network error')
    })

    it('handles unauthorized error', async () => {
      const error = new apiClient.ApiError(401, 'Unauthorized')
      mockApiGet.mockRejectedValue(error)

      await expect(referralApi.getInviteCodes()).rejects.toThrow('Unauthorized')
    })
  })

  describe('createInviteCode', () => {
    it('calls correct endpoint with POST method', async () => {
      const newCode = {
        id: 'new-code',
        code: 'NEW-CODE',
        max_uses: 10,
        current_uses: 0,
        is_active: true,
        expires_at: null,
        created_at: '2024-01-03T00:00:00Z',
      }
      mockApiPost.mockResolvedValue(newCode)

      const result = await referralApi.createInviteCode()

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/referral/codes')
      expect(result).toEqual(newCode)
    })

    it('does not send body data', async () => {
      mockApiPost.mockResolvedValue({})

      await referralApi.createInviteCode()

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/referral/codes')
    })

    it('propagates errors from API', async () => {
      const error = new Error('Creation failed')
      mockApiPost.mockRejectedValue(error)

      await expect(referralApi.createInviteCode()).rejects.toThrow('Creation failed')
    })

    it('handles limit reached error', async () => {
      const error = new apiClient.ApiError(400, 'Maximum invite codes reached')
      mockApiPost.mockRejectedValue(error)

      await expect(referralApi.createInviteCode()).rejects.toThrow(
        'Maximum invite codes reached'
      )
    })
  })

  describe('validateCode', () => {
    it('calls correct endpoint with code parameter', async () => {
      const validation = { valid: true, message: 'Valid code' }
      mockApiPost.mockResolvedValue(validation)

      const result = await referralApi.validateCode('ABCD-EFGH')

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/referral/codes/ABCD-EFGH/validate')
      expect(result).toEqual(validation)
    })

    it('handles valid code response', async () => {
      const validation = { valid: true, message: 'Valid invite code' }
      mockApiPost.mockResolvedValue(validation)

      const result = await referralApi.validateCode('VALID-CODE')

      expect(result.valid).toBe(true)
      expect(result.message).toBe('Valid invite code')
    })

    it('handles invalid code response', async () => {
      const validation = { valid: false, message: 'Invalid or expired code' }
      mockApiPost.mockResolvedValue(validation)

      const result = await referralApi.validateCode('INVALID')

      expect(result.valid).toBe(false)
      expect(result.message).toBe('Invalid or expired code')
    })

    it('handles codes with special characters', async () => {
      mockApiPost.mockResolvedValue({ valid: false, message: 'Invalid' })

      await referralApi.validateCode('TEST-CODE')

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/referral/codes/TEST-CODE/validate')
    })

    it('propagates validation errors', async () => {
      const error = new Error('Validation service unavailable')
      mockApiPost.mockRejectedValue(error)

      await expect(referralApi.validateCode('ABCD-EFGH')).rejects.toThrow(
        'Validation service unavailable'
      )
    })
  })

  describe('getStats', () => {
    it('calls correct endpoint', async () => {
      const stats = {
        total_invites: 10,
        successful_invites: 5,
        total_points: 100,
        available_points: 50,
      }
      mockApiGet.mockResolvedValue(stats)

      const result = await referralApi.getStats()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/referral/stats')
      expect(result).toEqual(stats)
    })

    it('returns zero values for new users', async () => {
      const stats = {
        total_invites: 0,
        successful_invites: 0,
        total_points: 0,
        available_points: 0,
      }
      mockApiGet.mockResolvedValue(stats)

      const result = await referralApi.getStats()

      expect(result.total_invites).toBe(0)
      expect(result.successful_invites).toBe(0)
      expect(result.total_points).toBe(0)
      expect(result.available_points).toBe(0)
    })

    it('propagates errors from API', async () => {
      const error = new Error('Stats unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(referralApi.getStats()).rejects.toThrow('Stats unavailable')
    })
  })

  describe('getRewards', () => {
    it('calls correct endpoint', async () => {
      const rewards = [
        {
          id: 'reward-1',
          reward_type: 'points' as const,
          amount: 100,
          source: 'invite',
          is_used: false,
          expires_at: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]
      mockApiGet.mockResolvedValue(rewards)

      const result = await referralApi.getRewards()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/referral/rewards')
      expect(result).toEqual(rewards)
    })

    it('returns empty array when no rewards', async () => {
      mockApiGet.mockResolvedValue([])

      const result = await referralApi.getRewards()

      expect(result).toEqual([])
    })

    it('handles multiple reward types', async () => {
      const rewards = [
        {
          id: 'reward-1',
          reward_type: 'points' as const,
          amount: 100,
          source: 'invite',
          is_used: false,
          expires_at: null,
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'reward-2',
          reward_type: 'pro_trial' as const,
          amount: 7,
          source: 'bonus',
          is_used: false,
          expires_at: '2024-12-31T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'reward-3',
          reward_type: 'credits' as const,
          amount: 50,
          source: 'referral',
          is_used: true,
          expires_at: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ]
      mockApiGet.mockResolvedValue(rewards)

      const result = await referralApi.getRewards()

      expect(result).toHaveLength(3)
      expect(result[0].reward_type).toBe('points')
      expect(result[1].reward_type).toBe('pro_trial')
      expect(result[2].reward_type).toBe('credits')
    })

    it('propagates errors from API', async () => {
      const error = new Error('Rewards service unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(referralApi.getRewards()).rejects.toThrow('Rewards service unavailable')
    })
  })

  describe('API Integration', () => {
    it('all methods return promises', () => {
      mockApiGet.mockResolvedValue([])
      mockApiPost.mockResolvedValue({})

      expect(referralApi.getInviteCodes()).toBeInstanceOf(Promise)
      expect(referralApi.createInviteCode()).toBeInstanceOf(Promise)
      expect(referralApi.validateCode('TEST')).toBeInstanceOf(Promise)
      expect(referralApi.getStats()).toBeInstanceOf(Promise)
      expect(referralApi.getRewards()).toBeInstanceOf(Promise)
    })

    it('uses correct HTTP methods for each operation', async () => {
      mockApiGet.mockResolvedValue([])
      mockApiPost.mockResolvedValue({})

      await referralApi.getInviteCodes()
      expect(mockApiGet).toHaveBeenCalled()

      await referralApi.createInviteCode()
      expect(mockApiPost).toHaveBeenCalled()

      await referralApi.validateCode('TEST')
      expect(mockApiPost).toHaveBeenCalled()

      await referralApi.getStats()
      expect(mockApiGet).toHaveBeenCalled()

      await referralApi.getRewards()
      expect(mockApiGet).toHaveBeenCalled()
    })
  })
})
