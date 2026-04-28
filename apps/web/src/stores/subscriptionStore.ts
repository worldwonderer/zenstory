/**
 * Subscription Store - Global state for subscription and quota management.
 */
import { create } from 'zustand';
import { subscriptionApi } from '../lib/subscriptionApi';
import type {
  SubscriptionStatusResponse,
  QuotaResponse,
  SubscriptionTier
} from '../types/subscription';

interface SubscriptionState {
  // Subscription status
  subscription: SubscriptionStatusResponse | null;
  quota: QuotaResponse | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchSubscription: () => Promise<void>;
  fetchQuota: () => Promise<void>;
  refresh: () => Promise<void>;

  // Helpers
  isPro: () => boolean;
  getTier: () => SubscriptionTier;
  getAiConversationsRemaining: () => number | null; // null = unlimited
}

export const useSubscriptionStore = create<SubscriptionState>((set, get) => ({
  subscription: null,
  quota: null,
  isLoading: false,
  error: null,

  fetchSubscription: async () => {
    try {
      set({ isLoading: true, error: null });
      const response = await subscriptionApi.getStatus();
      set({ subscription: response, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch subscription';
      set({ error: message, isLoading: false });
    }
  },

  fetchQuota: async () => {
    try {
      set({ isLoading: true, error: null });
      const response = await subscriptionApi.getQuota();
      set({ quota: response, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch quota';
      set({ error: message, isLoading: false });
    }
  },

  refresh: async () => {
    await Promise.all([get().fetchSubscription(), get().fetchQuota()]);
  },

  isPro: () => {
    const { subscription } = get();
    return subscription?.tier !== 'free';
  },

  getTier: () => {
    const { subscription } = get();
    return subscription?.tier ?? 'free';
  },

  getAiConversationsRemaining: () => {
    const { quota } = get();
    if (!quota) return null;

    const { used, limit } = quota.ai_conversations;
    if (limit === -1) return null; // Unlimited

    return Math.max(0, limit - used);
  },
}));

export default useSubscriptionStore;
