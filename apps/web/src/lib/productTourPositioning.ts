import type { ProductTourPlacement } from '../config/productTours/dashboardFirstRun';

export interface RectLike {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface ViewportLike {
  width: number;
  height: number;
}

export interface PointLike {
  top: number;
  left: number;
}

export interface CoachmarkPosition extends PointLike {
  placement: ProductTourPlacement;
}

const DEFAULT_MARGIN = 16;
const DEFAULT_GAP = 16;

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function getSpotlightRect(
  targetRect: RectLike,
  padding = 12,
  offsetX = 0,
  offsetY = 0,
): RectLike {
  return {
    top: Math.round(targetRect.top - padding + offsetY),
    left: Math.round(targetRect.left - padding + offsetX),
    width: Math.round(targetRect.width + padding * 2),
    height: Math.round(targetRect.height + padding * 2),
  };
}

function canPlace(
  placement: ProductTourPlacement,
  targetRect: RectLike,
  popoverSize: { width: number; height: number },
  viewport: ViewportLike,
  gap: number,
  margin: number,
): boolean {
  switch (placement) {
    case 'top':
      return targetRect.top - gap - popoverSize.height >= margin;
    case 'bottom':
      return targetRect.top + targetRect.height + gap + popoverSize.height <= viewport.height - margin;
    case 'left':
      return targetRect.left - gap - popoverSize.width >= margin;
    case 'right':
      return targetRect.left + targetRect.width + gap + popoverSize.width <= viewport.width - margin;
    case 'center':
      return true;
    default:
      return true;
  }
}

function getFallbackPlacement(preferred: ProductTourPlacement): ProductTourPlacement[] {
  switch (preferred) {
    case 'top':
      return ['top', 'bottom', 'right', 'left'];
    case 'bottom':
      return ['bottom', 'top', 'right', 'left'];
    case 'left':
      return ['left', 'right', 'bottom', 'top'];
    case 'right':
      return ['right', 'left', 'bottom', 'top'];
    case 'center':
    default:
      return ['center'];
  }
}

export function getCoachmarkPosition({
  targetRect,
  popoverSize,
  viewport,
  placement = 'bottom',
  margin = DEFAULT_MARGIN,
  gap = DEFAULT_GAP,
}: {
  targetRect: RectLike;
  popoverSize: { width: number; height: number };
  viewport: ViewportLike;
  placement?: ProductTourPlacement;
  margin?: number;
  gap?: number;
}): CoachmarkPosition {
  const resolvedPlacement = getFallbackPlacement(placement).find((candidate) =>
    canPlace(candidate, targetRect, popoverSize, viewport, gap, margin),
  ) ?? 'center';

  if (resolvedPlacement === 'center') {
    return {
      top: clamp((viewport.height - popoverSize.height) / 2, margin, Math.max(margin, viewport.height - popoverSize.height - margin)),
      left: clamp((viewport.width - popoverSize.width) / 2, margin, Math.max(margin, viewport.width - popoverSize.width - margin)),
      placement: resolvedPlacement,
    };
  }

  const centeredLeft = targetRect.left + targetRect.width / 2 - popoverSize.width / 2;
  const centeredTop = targetRect.top + targetRect.height / 2 - popoverSize.height / 2;

  switch (resolvedPlacement) {
    case 'top':
      return {
        top: clamp(targetRect.top - popoverSize.height - gap, margin, viewport.height - popoverSize.height - margin),
        left: clamp(centeredLeft, margin, viewport.width - popoverSize.width - margin),
        placement: resolvedPlacement,
      };
    case 'bottom':
      return {
        top: clamp(targetRect.top + targetRect.height + gap, margin, viewport.height - popoverSize.height - margin),
        left: clamp(centeredLeft, margin, viewport.width - popoverSize.width - margin),
        placement: resolvedPlacement,
      };
    case 'left':
      return {
        top: clamp(centeredTop, margin, viewport.height - popoverSize.height - margin),
        left: clamp(targetRect.left - popoverSize.width - gap, margin, viewport.width - popoverSize.width - margin),
        placement: resolvedPlacement,
      };
    case 'right':
    default:
      return {
        top: clamp(centeredTop, margin, viewport.height - popoverSize.height - margin),
        left: clamp(targetRect.left + targetRect.width + gap, margin, viewport.width - popoverSize.width - margin),
        placement: resolvedPlacement,
      };
  }
}

export function isRectInViewport(targetRect: RectLike, viewport: ViewportLike): boolean {
  return (
    targetRect.top >= 0
    && targetRect.left >= 0
    && targetRect.top + targetRect.height <= viewport.height
    && targetRect.left + targetRect.width <= viewport.width
  );
}
