export const PRODUCT_TOUR_STORAGE_PREFIX = 'zenstory:tours:v1';

export interface ProductTourState {
  version: number;
  completed: boolean;
  dismissed: boolean;
  currentStepId: string | null;
  updatedAt: string;
}

type ProductTourStateMap = Record<string, ProductTourState>;

function buildStorageKey(userId: string): string {
  return `${PRODUCT_TOUR_STORAGE_PREFIX}:${userId}`;
}

function isProductTourState(value: unknown): value is ProductTourState {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<ProductTourState>;
  return (
    typeof candidate.version === 'number'
    && typeof candidate.completed === 'boolean'
    && typeof candidate.dismissed === 'boolean'
    && (candidate.currentStepId === null || typeof candidate.currentStepId === 'string')
    && typeof candidate.updatedAt === 'string'
  );
}

export function createDefaultProductTourState(version: number, currentStepId: string | null = null): ProductTourState {
  return {
    version,
    completed: false,
    dismissed: false,
    currentStepId,
    updatedAt: new Date().toISOString(),
  };
}

export function getProductTourState(userId: string | null | undefined, tourId: string): ProductTourState | null {
  if (!userId) return null;

  try {
    const raw = localStorage.getItem(buildStorageKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const candidate = parsed[tourId];
    return isProductTourState(candidate) ? candidate : null;
  } catch {
    return null;
  }
}

export function saveProductTourState(userId: string | null | undefined, tourId: string, state: ProductTourState): ProductTourState | null {
  if (!userId) return null;

  try {
    const raw = localStorage.getItem(buildStorageKey(userId));
    const existing = raw ? (JSON.parse(raw) as ProductTourStateMap) : {};
    existing[tourId] = state;
    localStorage.setItem(buildStorageKey(userId), JSON.stringify(existing));
    return state;
  } catch {
    return null;
  }
}

export function markProductTourCompleted(
  userId: string | null | undefined,
  tourId: string,
  version: number,
): ProductTourState | null {
  const nextState: ProductTourState = {
    version,
    completed: true,
    dismissed: false,
    currentStepId: null,
    updatedAt: new Date().toISOString(),
  };
  return saveProductTourState(userId, tourId, nextState);
}

export function dismissProductTour(
  userId: string | null | undefined,
  tourId: string,
  version: number,
  currentStepId: string | null = null,
): ProductTourState | null {
  const nextState: ProductTourState = {
    version,
    completed: false,
    dismissed: true,
    currentStepId,
    updatedAt: new Date().toISOString(),
  };
  return saveProductTourState(userId, tourId, nextState);
}

export function resetProductTour(userId: string | null | undefined, tourId: string): void {
  if (!userId) return;

  try {
    const raw = localStorage.getItem(buildStorageKey(userId));
    if (!raw) return;
    const existing = JSON.parse(raw) as ProductTourStateMap;
    delete existing[tourId];
    if (Object.keys(existing).length === 0) {
      localStorage.removeItem(buildStorageKey(userId));
      return;
    }
    localStorage.setItem(buildStorageKey(userId), JSON.stringify(existing));
  } catch {
    // no-op
  }
}
