import { describe, it, expect, vi, beforeEach } from 'vitest'
import { pointsApi } from '../pointsApi'
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

describe('pointsApi', () => {
  const mockApiGet = vi.mocked(apiClient.api.get)
  const mockApiPost = vi.mocked(apiClient.api.post)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getBalance', () => {
    it('calls correct endpoint', async () => {
      const mockBalance = {
        available: 1000,
        pending_expiration: 100,
        nearest_expiration_date: '2024-12-31T00:00:00Z',
      }
      mockApiGet.mockResolvedValue(mockBalance)

      const result = await pointsApi.getBalance()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/balance')
      expect(result).toEqual(mockBalance)
    })

    it('returns zero balance for new users', async () => {
      const mockBalance = {
        available: 0,
        pending_expiration: 0,
        nearest_expiration_date: null,
      }
      mockApiGet.mockResolvedValue(mockBalance)

      const result = await pointsApi.getBalance()

      expect(result.available).toBe(0)
      expect(result.pending_expiration).toBe(0)
      expect(result.nearest_expiration_date).toBeNull()
    })

    it('propagates errors from API', async () => {
      const error = new Error('Network error')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getBalance()).rejects.toThrow('Network error')
    })

    it('handles unauthorized error', async () => {
      const error = new apiClient.ApiError(401, 'Unauthorized')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getBalance()).rejects.toThrow('Unauthorized')
    })
  })

  describe('checkIn', () => {
    it('calls correct endpoint with POST method', async () => {
      const mockResponse = {
        success: true,
        points_earned: 10,
        streak_days: 5,
        message: '签到成功！获得 10 积分',
      }
      mockApiPost.mockResolvedValue(mockResponse)

      const result = await pointsApi.checkIn()

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/points/check-in')
      expect(result).toEqual(mockResponse)
    })

    it('returns streak bonus for consecutive days', async () => {
      const mockResponse = {
        success: true,
        points_earned: 15,
        streak_days: 7,
        message: '签到成功！连续 7 天，获得 15 积分',
      }
      mockApiPost.mockResolvedValue(mockResponse)

      const result = await pointsApi.checkIn()

      expect(result.success).toBe(true)
      expect(result.points_earned).toBe(15)
      expect(result.streak_days).toBe(7)
    })

    it('handles already checked in error', async () => {
      const error = new apiClient.ApiError(400, '今日已签到')
      mockApiPost.mockRejectedValue(error)

      await expect(pointsApi.checkIn()).rejects.toThrow('今日已签到')
    })

    it('propagates errors from API', async () => {
      const error = new Error('Check-in failed')
      mockApiPost.mockRejectedValue(error)

      await expect(pointsApi.checkIn()).rejects.toThrow('Check-in failed')
    })
  })

  describe('getCheckInStatus', () => {
    it('calls correct endpoint', async () => {
      const mockStatus = {
        checked_in: true,
        streak_days: 5,
        points_earned_today: 10,
      }
      mockApiGet.mockResolvedValue(mockStatus)

      const result = await pointsApi.getCheckInStatus()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/check-in/status')
      expect(result).toEqual(mockStatus)
    })

    it('returns not checked in status', async () => {
      const mockStatus = {
        checked_in: false,
        streak_days: 0,
        points_earned_today: 0,
      }
      mockApiGet.mockResolvedValue(mockStatus)

      const result = await pointsApi.getCheckInStatus()

      expect(result.checked_in).toBe(false)
      expect(result.streak_days).toBe(0)
    })

    it('returns checked in status with streak', async () => {
      const mockStatus = {
        checked_in: true,
        streak_days: 10,
        points_earned_today: 20,
      }
      mockApiGet.mockResolvedValue(mockStatus)

      const result = await pointsApi.getCheckInStatus()

      expect(result.checked_in).toBe(true)
      expect(result.streak_days).toBe(10)
      expect(result.points_earned_today).toBe(20)
    })

    it('propagates errors from API', async () => {
      const error = new Error('Status unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getCheckInStatus()).rejects.toThrow('Status unavailable')
    })
  })

  describe('getTransactions', () => {
    it('calls correct endpoint with default pagination', async () => {
      const mockResponse = {
        transactions: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      }
      mockApiGet.mockResolvedValue(mockResponse)

      const result = await pointsApi.getTransactions()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/transactions?page=1&page_size=20')
      expect(result).toEqual(mockResponse)
    })

    it('calls correct endpoint with custom pagination', async () => {
      const mockResponse = {
        transactions: [],
        total: 100,
        page: 2,
        page_size: 50,
        total_pages: 2,
      }
      mockApiGet.mockResolvedValue(mockResponse)

      const result = await pointsApi.getTransactions(2, 50)

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/transactions?page=2&page_size=50')
      expect(result.page).toBe(2)
      expect(result.page_size).toBe(50)
    })

    it('returns transaction list correctly', async () => {
      const mockResponse = {
        transactions: [
          {
            id: 'txn-1',
            amount: 10,
            balance_after: 1010,
            transaction_type: 'check_in',
            source_id: null,
            description: '每日签到',
            expires_at: null,
            is_expired: false,
            created_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'txn-2',
            amount: -100,
            balance_after: 910,
            transaction_type: 'redeem_pro',
            source_id: null,
            description: '兑换 Pro 会员 7 天',
            expires_at: null,
            is_expired: false,
            created_at: '2024-01-02T00:00:00Z',
          },
        ],
        total: 2,
        page: 1,
        page_size: 20,
        total_pages: 1,
      }
      mockApiGet.mockResolvedValue(mockResponse)

      const result = await pointsApi.getTransactions()

      expect(result.transactions).toHaveLength(2)
      expect(result.transactions[0].amount).toBe(10)
      expect(result.transactions[1].amount).toBe(-100)
    })

    it('propagates errors from API', async () => {
      const error = new Error('Transactions unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getTransactions()).rejects.toThrow('Transactions unavailable')
    })
  })

  describe('redeemForPro', () => {
    it('calls correct endpoint with days parameter', async () => {
      const mockResponse = {
        success: true,
        points_spent: 100,
        pro_days: 7,
        new_period_end: '2024-02-01T00:00:00Z',
      }
      mockApiPost.mockResolvedValue(mockResponse)

      const result = await pointsApi.redeemForPro(7)

      expect(mockApiPost).toHaveBeenCalledWith('/api/v1/points/redeem', { days: 7 })
      expect(result).toEqual(mockResponse)
    })

    it('returns success response for valid redemption', async () => {
      const mockResponse = {
        success: true,
        points_spent: 200,
        pro_days: 14,
        new_period_end: '2024-02-15T00:00:00Z',
      }
      mockApiPost.mockResolvedValue(mockResponse)

      const result = await pointsApi.redeemForPro(14)

      expect(result.success).toBe(true)
      expect(result.points_spent).toBe(200)
      expect(result.pro_days).toBe(14)
    })

    it('handles insufficient points error', async () => {
      const error = new apiClient.ApiError(400, '积分不足')
      mockApiPost.mockRejectedValue(error)

      await expect(pointsApi.redeemForPro(7)).rejects.toThrow('积分不足')
    })

    it('propagates errors from API', async () => {
      const error = new Error('Redemption failed')
      mockApiPost.mockRejectedValue(error)

      await expect(pointsApi.redeemForPro(7)).rejects.toThrow('Redemption failed')
    })
  })

  describe('getEarnOpportunities', () => {
    it('calls correct endpoint', async () => {
      const mockOpportunities = [
        {
          type: 'check_in',
          points: 10,
          description: '每日签到',
          is_completed: false,
          is_available: true,
        },
        {
          type: 'profile_complete',
          points: 50,
          description: '完善个人资料',
          is_completed: true,
          is_available: false,
        },
      ]
      mockApiGet.mockResolvedValue(mockOpportunities)

      const result = await pointsApi.getEarnOpportunities()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/earn-opportunities')
      expect(result).toEqual(mockOpportunities)
    })

    it('returns empty array when no opportunities', async () => {
      mockApiGet.mockResolvedValue([])

      const result = await pointsApi.getEarnOpportunities()

      expect(result).toEqual([])
    })

    it('handles multiple opportunity types', async () => {
      const mockOpportunities = [
        {
          type: 'check_in',
          points: 10,
          description: '每日签到',
          is_completed: false,
          is_available: true,
        },
        {
          type: 'referral',
          points: 100,
          description: '邀请好友',
          is_completed: false,
          is_available: true,
        },
        {
          type: 'skill_contribution',
          points: 50,
          description: '贡献技能包',
          is_completed: false,
          is_available: true,
        },
      ]
      mockApiGet.mockResolvedValue(mockOpportunities)

      const result = await pointsApi.getEarnOpportunities()

      expect(result).toHaveLength(3)
      expect(result[0].type).toBe('check_in')
      expect(result[1].type).toBe('referral')
      expect(result[2].type).toBe('skill_contribution')
    })

    it('propagates errors from API', async () => {
      const error = new Error('Opportunities unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getEarnOpportunities()).rejects.toThrow('Opportunities unavailable')
    })
  })

  describe('getConfig', () => {
    it('calls correct endpoint', async () => {
      const mockConfig = {
        check_in: 10,
        check_in_streak: 5,
        referral: 100,
        skill_contribution: 50,
        inspiration_contribution: 30,
        profile_complete: 50,
        pro_7days_cost: 100,
        streak_bonus_threshold: 7,
      }
      mockApiGet.mockResolvedValue(mockConfig)

      const result = await pointsApi.getConfig()

      expect(mockApiGet).toHaveBeenCalledWith('/api/v1/points/config')
      expect(result).toEqual(mockConfig)
    })

    it('returns all config values', async () => {
      const mockConfig = {
        check_in: 10,
        check_in_streak: 5,
        referral: 100,
        skill_contribution: 50,
        inspiration_contribution: 30,
        profile_complete: 50,
        pro_7days_cost: 100,
        streak_bonus_threshold: 7,
      }
      mockApiGet.mockResolvedValue(mockConfig)

      const result = await pointsApi.getConfig()

      expect(result.check_in).toBe(10)
      expect(result.check_in_streak).toBe(5)
      expect(result.referral).toBe(100)
      expect(result.pro_7days_cost).toBe(100)
    })

    it('propagates errors from API', async () => {
      const error = new Error('Config unavailable')
      mockApiGet.mockRejectedValue(error)

      await expect(pointsApi.getConfig()).rejects.toThrow('Config unavailable')
    })
  })

  describe('API Integration', () => {
    it('all methods return promises', () => {
      mockApiGet.mockResolvedValue({})
      mockApiPost.mockResolvedValue({})

      expect(pointsApi.getBalance()).toBeInstanceOf(Promise)
      expect(pointsApi.checkIn()).toBeInstanceOf(Promise)
      expect(pointsApi.getCheckInStatus()).toBeInstanceOf(Promise)
      expect(pointsApi.getTransactions()).toBeInstanceOf(Promise)
      expect(pointsApi.redeemForPro(7)).toBeInstanceOf(Promise)
      expect(pointsApi.getEarnOpportunities()).toBeInstanceOf(Promise)
      expect(pointsApi.getConfig()).toBeInstanceOf(Promise)
    })

    it('uses correct HTTP methods for each operation', async () => {
      mockApiGet.mockResolvedValue({})
      mockApiPost.mockResolvedValue({})

      await pointsApi.getBalance()
      expect(mockApiGet).toHaveBeenCalled()

      await pointsApi.checkIn()
      expect(mockApiPost).toHaveBeenCalled()

      await pointsApi.getCheckInStatus()
      expect(mockApiGet).toHaveBeenCalled()

      await pointsApi.getTransactions()
      expect(mockApiGet).toHaveBeenCalled()

      await pointsApi.redeemForPro(7)
      expect(mockApiPost).toHaveBeenCalled()

      await pointsApi.getEarnOpportunities()
      expect(mockApiGet).toHaveBeenCalled()

      await pointsApi.getConfig()
      expect(mockApiGet).toHaveBeenCalled()
    })
  })
})
