import { describe, expect, it } from 'vitest';
import {
  getCoachmarkPosition,
  getSpotlightRect,
  isRectInViewport,
} from '../productTourPositioning';

describe('productTourPositioning', () => {
  it('expands spotlight rect with padding', () => {
    expect(getSpotlightRect({ top: 20, left: 30, width: 100, height: 40 }, 10)).toEqual({
      top: 10,
      left: 20,
      width: 120,
      height: 60,
    });
  });

  it('falls back from preferred placement when there is no room', () => {
    const position = getCoachmarkPosition({
      targetRect: { top: 8, left: 200, width: 120, height: 48 },
      popoverSize: { width: 320, height: 180 },
      viewport: { width: 1280, height: 900 },
      placement: 'top',
    });

    expect(position.placement).toBe('bottom');
    expect(position.top).toBeGreaterThan(40);
  });

  it('keeps positions inside the viewport bounds', () => {
    const position = getCoachmarkPosition({
      targetRect: { top: 300, left: 1100, width: 120, height: 48 },
      popoverSize: { width: 320, height: 180 },
      viewport: { width: 1280, height: 900 },
      placement: 'right',
    });

    expect(position.left).toBeLessThanOrEqual(1280 - 320 - 16);
  });

  it('detects whether a rect is fully inside viewport', () => {
    expect(isRectInViewport({ top: 10, left: 10, width: 100, height: 100 }, { width: 500, height: 500 })).toBe(true);
    expect(isRectInViewport({ top: -1, left: 10, width: 100, height: 100 }, { width: 500, height: 500 })).toBe(false);
  });
});
