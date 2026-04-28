// ==================== Referral / Invite Code Types ====================

/**
 * Invite code for user referral system
 */
export interface InviteCode {
  id: string;
  code: string;
  max_uses: number;
  current_uses: number;
  is_active: boolean;
  expires_at: string | null;
  created_at: string;
}

/**
 * Referral statistics for current user
 */
export interface ReferralStats {
  total_invites: number;
  successful_invites: number;
  total_points: number;
  available_points: number;
}

/**
 * User reward from referral system
 */
export interface UserReward {
  id: string;
  reward_type: 'points' | 'pro_trial' | 'credits';
  amount: number;
  source: string;
  is_used: boolean;
  expires_at: string | null;
  created_at: string;
}

/**
 * Invite code validation result
 */
export interface InviteCodeValidation {
  valid: boolean;
  message: string;
}
