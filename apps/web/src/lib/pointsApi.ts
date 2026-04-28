/**
 * Points API client for managing user points, check-ins, and rewards.
 *
 * Provides functions for:
 * - Querying points balance and transaction history
 * - Daily check-in functionality with streak tracking
 * - Redeeming points for Pro subscription
 * - Viewing earn opportunities and configuration
 */

import { api } from './apiClient';
import type {
  PointsBalance,
  CheckInResponse,
  CheckInStatusResponse,
  TransactionHistoryResponse,
  EarnOpportunity,
  RedeemProResponse,
  PointsConfig,
} from '../types/points';

export const pointsApi = {
  /**
   * Get the current user's points balance.
   *
   * @returns Promise resolving to the points balance including total points and pending points
   */
  getBalance: () =>
    api.get<PointsBalance>('/api/v1/points/balance'),

  /**
   * Perform daily check-in to earn points.
   *
   * Awards points based on consecutive check-in streak.
   * Bonus points are given for milestone streaks (7, 14, 30 days).
   *
   * @returns Promise resolving to check-in result with earned points and streak info
   */
  checkIn: () =>
    api.post<CheckInResponse>('/api/v1/points/check-in'),

  /**
   * Get the check-in status for the current day.
   *
   * @returns Promise resolving to whether user has checked in today and current streak
   */
  getCheckInStatus: () =>
    api.get<CheckInStatusResponse>('/api/v1/points/check-in/status'),

  /**
   * Get paginated transaction history for points.
   *
   * @param page - Page number for pagination (1-indexed)
   * @param pageSize - Number of transactions per page
   * @returns Promise resolving to paginated list of point transactions with totals
   */
  getTransactions: (page = 1, pageSize = 20) =>
    api.get<TransactionHistoryResponse>(
      `/api/v1/points/transactions?page=${page}&page_size=${pageSize}`
    ),

  /**
   * Redeem points for Pro subscription days.
   *
   * @param days - Number of Pro subscription days to redeem (7, 14, or 30)
   * @returns Promise resolving to redemption result with new subscription expiry date
   */
  redeemForPro: (days: number) =>
    api.post<RedeemProResponse>('/api/v1/points/redeem', { days }),

  /**
   * Get available earn opportunities for the user.
   *
   * Returns list of actions that can earn points (e.g., first project,
   * daily check-in streaks, referrals) with their point values.
   *
   * @returns Promise resolving to array of earn opportunity objects
   */
  getEarnOpportunities: () =>
    api.get<EarnOpportunity[]>('/api/v1/points/earn-opportunities'),

  /**
   * Get public points system configuration.
   *
   * Returns exchange rates, check-in rewards, and other configurable parameters.
   *
   * @returns Promise resolving to points configuration settings
   */
  getConfig: () =>
    api.get<PointsConfig>('/api/v1/points/config'),
};

export default pointsApi;
