/**
 * Referral API client for managing invite codes and referral rewards.
 *
 * Provides functions for:
 * - Creating and managing invite codes
 * - Validating invite codes during registration
 * - Tracking referral statistics and earned rewards
 */

import { api } from './apiClient';
import type { InviteCode, ReferralStats, UserReward, InviteCodeValidation } from '@/types/referral';

export const referralApi = {
  /**
   * Get all invite codes created by the current user.
   *
   * Returns both active and expired codes with their usage statistics.
   *
   * @returns Promise resolving to array of invite code objects
   */
  getInviteCodes: () =>
    api.get<InviteCode[]>('/api/v1/referral/codes'),

  /**
   * Create a new invite code for referrals.
   *
   * Each user can create a limited number of active codes.
   * The code can be shared with others to earn referral rewards.
   *
   * @returns Promise resolving to the newly created invite code
   */
  createInviteCode: () =>
    api.post<InviteCode>('/api/v1/referral/codes'),

  /**
   * Validate an invite code before registration.
   *
   * Checks if the code is valid, active, and not expired.
   * Used during the registration flow to apply referral benefits.
   *
   * @param code - The invite code string to validate
   * @returns Promise resolving to validation result with code details if valid
   */
  validateCode: (code: string) =>
    api.post<InviteCodeValidation>(`/api/v1/referral/codes/${code}/validate`),

  /**
   * Get referral statistics for the current user.
   *
   * Returns total referrals, successful sign-ups, and pending invitations.
   *
   * @returns Promise resolving to referral statistics summary
   */
  getStats: () =>
    api.get<ReferralStats>('/api/v1/referral/stats'),

  /**
   * Get rewards earned through the referral program.
   *
   * Returns both claimed and pending rewards from successful referrals.
   *
   * @returns Promise resolving to array of reward records with status
   */
  getRewards: () =>
    api.get<UserReward[]>('/api/v1/referral/rewards'),
};

export default referralApi;
