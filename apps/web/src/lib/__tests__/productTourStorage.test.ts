import {
  PRODUCT_TOUR_STORAGE_PREFIX,
  createDefaultProductTourState,
  dismissProductTour,
  getProductTourState,
  markProductTourCompleted,
  resetProductTour,
  saveProductTourState,
} from '../productTourStorage';
import { afterEach, describe, expect, it } from 'vitest';

describe('productTourStorage', () => {
  const userId = 'user-tour-1';
  const tourId = 'dashboard_first_run';
  const storageKey = `${PRODUCT_TOUR_STORAGE_PREFIX}:${userId}`;

  afterEach(() => {
    localStorage.clear();
  });

  it('creates a default state', () => {
    const state = createDefaultProductTourState(1, 'step-a');
    expect(state.version).toBe(1);
    expect(state.currentStepId).toBe('step-a');
    expect(state.completed).toBe(false);
    expect(state.dismissed).toBe(false);
  });

  it('saves and reads tour state by user and tour id', () => {
    const state = createDefaultProductTourState(1, 'step-b');
    saveProductTourState(userId, tourId, state);

    expect(getProductTourState(userId, tourId)).toEqual(state);
    expect(JSON.parse(localStorage.getItem(storageKey) || '{}')[tourId]).toEqual(state);
  });

  it('marks a tour as completed', () => {
    const state = markProductTourCompleted(userId, tourId, 1);
    expect(state?.completed).toBe(true);
    expect(state?.dismissed).toBe(false);
    expect(state?.currentStepId).toBeNull();
  });

  it('dismisses and resets a tour', () => {
    dismissProductTour(userId, tourId, 1, 'step-c');
    expect(getProductTourState(userId, tourId)?.dismissed).toBe(true);

    resetProductTour(userId, tourId);
    expect(getProductTourState(userId, tourId)).toBeNull();
    expect(localStorage.getItem(storageKey)).toBeNull();
  });
});
