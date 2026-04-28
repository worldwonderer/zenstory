/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useLocation } from 'react-router-dom';
import type { ProductTourDefinition, ProductTourStep } from '../config/productTours/dashboardFirstRun';
import { useIsMobile } from '../hooks/useMediaQuery';
import { trackEvent } from '../lib/analytics';
import {
  createDefaultProductTourState,
  dismissProductTour,
  getProductTourState,
  markProductTourCompleted,
  resetProductTour,
  saveProductTourState,
  type ProductTourState,
} from '../lib/productTourStorage';
import { isRectInViewport } from '../lib/productTourPositioning';

interface ResolvedTarget {
  element: HTMLElement;
  rect: DOMRect;
}

interface ProductTourContextValue {
  tourId: string;
  isEnabled: boolean;
  isEligible: boolean;
  isActive: boolean;
  currentStep: ProductTourStep | null;
  currentStepIndex: number;
  totalSteps: number;
  targetElement: HTMLElement | null;
  targetRect: DOMRect | null;
  startTour: () => void;
  restartTour: () => void;
  nextStep: () => void;
  previousStep: () => void;
  skipTour: () => void;
  finishTour: () => void;
}

const ProductTourContext = createContext<ProductTourContextValue | null>(null);

function persistState(
  userId: string | null | undefined,
  tour: ProductTourDefinition,
  nextState: ProductTourState,
): ProductTourState {
  saveProductTourState(userId, tour.id, nextState);
  return nextState;
}

export function ProductTourProvider({
  children,
  tour,
  userId,
  enabled,
  eligible,
  autoStartReason,
  autoStartDelayMs = 900,
}: {
  children: ReactNode;
  tour: ProductTourDefinition;
  userId: string | null | undefined;
  enabled: boolean;
  eligible: boolean;
  autoStartReason?: string | null;
  autoStartDelayMs?: number;
}) {
  const location = useLocation();
  const isMobileViewport = useIsMobile();
  const effectiveAutoStartDelayMs = import.meta.env.MODE === 'test' ? 0 : autoStartDelayMs;
  const initialState = useMemo(
    () => getProductTourState(userId, tour.id) ?? createDefaultProductTourState(tour.version),
    [tour.id, tour.version, userId],
  );
  const [tourState, setTourState] = useState<ProductTourState>(initialState);
  const [resolvedTarget, setResolvedTarget] = useState<ResolvedTarget | null>(null);
  const lastViewedStepRef = useRef<string | null>(null);
  const clearResolvedTarget = useCallback(() => {
    window.requestAnimationFrame(() => {
      setResolvedTarget(null);
    });
  }, []);
  const currentStepIndex = useMemo(
    () => tour.steps.findIndex((step) => step.id === tourState.currentStepId),
    [tour.steps, tourState.currentStepId],
  );
  const currentStep = currentStepIndex >= 0 ? tour.steps[currentStepIndex] : null;
  const isActive = Boolean(enabled && currentStep && !tourState.completed && !tourState.dismissed);

  const updateTourState = useCallback((updater: (current: ProductTourState) => ProductTourState) => {
    setTourState((current) => {
      const nextState = updater(current);
      return persistState(userId, tour, nextState);
    });
  }, [tour, userId]);

  const finishTour = useCallback(() => {
    const completedState = markProductTourCompleted(userId, tour.id, tour.version)
      ?? {
        version: tour.version,
        completed: true,
        dismissed: false,
        currentStepId: null,
        updatedAt: new Date().toISOString(),
      };
    setTourState(completedState);
    trackEvent('tour_completed', {
      tour_id: tour.id,
      route: location.pathname,
    });
  }, [location.pathname, tour.id, tour.version, userId]);

  const startTour = useCallback(() => {
    const firstStep = tour.steps[0];
    if (!firstStep) return;

    const nextState = createDefaultProductTourState(tour.version, firstStep.id);
    persistState(userId, tour, nextState);
    setTourState(nextState);
    trackEvent('tour_started', {
      tour_id: tour.id,
      step_id: firstStep.id,
      route: location.pathname,
    });
  }, [location.pathname, tour, userId]);

  const restartTour = useCallback(() => {
    resetProductTour(userId, tour.id);
    startTour();
  }, [startTour, tour.id, userId]);

  const resolveNextStepDefinition = useCallback(() => {
    if (currentStepIndex < 0 || !currentStep) {
      return null;
    }

    if (currentStep.id === 'inspiration_input') {
      const input = document.querySelector<HTMLTextAreaElement>('[data-tour-id="dashboard-inspiration-input"]');
      const hasIdea = Boolean(input?.value.trim());
      const nextStepId = hasIdea ? 'create_project' : 'inspirations_link';
      return tour.steps.find((step) => step.id === nextStepId) ?? null;
    }

    if (currentStep.id === 'inspirations_link') {
      return tour.steps.find((step) => step.id === 'create_project') ?? null;
    }

    return tour.steps[currentStepIndex + 1] ?? null;
  }, [currentStep, currentStepIndex, tour.steps]);

  const nextStep = useCallback(() => {
    const nextStepDefinition = resolveNextStepDefinition();
    if (!nextStepDefinition) {
      finishTour();
      return;
    }

    updateTourState(() => ({
      version: tour.version,
      completed: false,
      dismissed: false,
      currentStepId: nextStepDefinition.id,
      updatedAt: new Date().toISOString(),
    }));
  }, [finishTour, resolveNextStepDefinition, tour.version, updateTourState]);

  const previousStep = useCallback(() => {
    if (currentStepIndex <= 0) return;
    const previous = tour.steps[currentStepIndex - 1];
    updateTourState(() => ({
      version: tour.version,
      completed: false,
      dismissed: false,
      currentStepId: previous.id,
      updatedAt: new Date().toISOString(),
    }));
  }, [currentStepIndex, tour.steps, tour.version, updateTourState]);

  const skipTour = useCallback(() => {
    const dismissedState = dismissProductTour(userId, tour.id, tour.version, currentStep?.id ?? null)
      ?? {
        version: tour.version,
        completed: false,
        dismissed: true,
        currentStepId: currentStep?.id ?? null,
        updatedAt: new Date().toISOString(),
      };
    setTourState(dismissedState);
    trackEvent('tour_skipped', {
      tour_id: tour.id,
      step_id: currentStep?.id,
      route: location.pathname,
    });
  }, [currentStep?.id, location.pathname, tour.id, tour.version, userId]);

  useEffect(() => {
    if (!enabled || !eligible || !autoStartReason || tourState.completed || tourState.dismissed || currentStep) {
      return;
    }
    const firstStep = tour.steps[0];
    if (!firstStep || location.pathname !== firstStep.route) {
      return;
    }

    let cancelled = false;
    let suppressedReason: string | null = null;
    const initialScrollY = window.scrollY;

    const suppress = (reason: string) => {
      if (suppressedReason) return;
      suppressedReason = reason;
      trackEvent('tour_suppressed', {
        tour_id: tour.id,
        route: location.pathname,
        reason,
        auto_start_reason: autoStartReason,
      });
    };

    const handlePointerDown = () => suppress('pointerdown_before_autostart');
    const handleKeyDown = () => suppress('keydown_before_autostart');
    const handleScroll = () => {
      if (Math.abs(window.scrollY - initialScrollY) > 32) {
        suppress('scroll_before_autostart');
      }
    };

    document.addEventListener('pointerdown', handlePointerDown, true);
    document.addEventListener('keydown', handleKeyDown, true);
    window.addEventListener('scroll', handleScroll, { passive: true });

    const timer = window.setTimeout(() => {
      if (cancelled || suppressedReason) return;
      if (document.querySelector('[role="dialog"][aria-modal="true"]')) {
        suppress('blocking_dialog_visible');
        return;
      }

      trackEvent('tour_eligible', {
        tour_id: tour.id,
        route: location.pathname,
        auto_start_reason: autoStartReason,
      });
      startTour();
    }, effectiveAutoStartDelayMs);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener('pointerdown', handlePointerDown, true);
      document.removeEventListener('keydown', handleKeyDown, true);
      window.removeEventListener('scroll', handleScroll);
    };
  }, [
    effectiveAutoStartDelayMs,
    autoStartReason,
    currentStep,
    eligible,
    enabled,
    location.pathname,
    startTour,
    tour.id,
    tour.steps,
    tourState.completed,
    tourState.dismissed,
  ]);

  useEffect(() => {
    if (!isActive || !currentStep) {
      clearResolvedTarget();
      return;
    }

    if (location.pathname !== currentStep.route) {
      clearResolvedTarget();
      return;
    }

    let cancelled = false;
    let attempts = 0;
    let timerId: number | null = null;

    const resolveTarget = () => {
      if (cancelled) return;
      const targetId = isMobileViewport && currentStep.mobileTargetId ? currentStep.mobileTargetId : currentStep.targetId;
      const element = document.querySelector<HTMLElement>(`[data-tour-id="${targetId}"]`);
      if (element) {
        const rect = element.getBoundingClientRect();
        if (isMobileViewport) {
          const absoluteTop = window.scrollY + rect.top;
          const desiredTopOffset = 112;
          const targetScrollTop = Math.max(0, absoluteTop - desiredTopOffset);
          window.scrollTo({ top: targetScrollTop, behavior: 'auto' });
          timerId = window.setTimeout(() => {
            if (cancelled) return;
            setResolvedTarget({ element, rect: element.getBoundingClientRect() });
          }, 80);
          return;
        }

        if (!isRectInViewport(rect, { width: window.innerWidth, height: window.innerHeight })) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
        }
        setResolvedTarget({ element, rect: element.getBoundingClientRect() });
        return;
      }

      attempts += 1;
      if (attempts < 20 && currentStep.ifMissing === 'wait') {
        timerId = window.setTimeout(resolveTarget, 120);
        return;
      }

      if (currentStep.ifMissing === 'skip') {
        timerId = window.setTimeout(() => nextStep(), 0);
        return;
      }

      if (currentStep.ifMissing === 'abort') {
        timerId = window.setTimeout(() => skipTour(), 0);
      }
    };

    resolveTarget();

    return () => {
      cancelled = true;
      if (timerId) {
        window.clearTimeout(timerId);
      }
    };
  }, [clearResolvedTarget, currentStep, isActive, isMobileViewport, location.pathname, nextStep, skipTour]);

  useEffect(() => {
    if (!resolvedTarget?.element || !isActive) {
      return;
    }

    const updateRect = () => {
      setResolvedTarget((current) => {
        if (!current?.element) return current;
        return {
          element: current.element,
          rect: current.element.getBoundingClientRect(),
        };
      });
    };

    updateRect();
    const observer = new ResizeObserver(updateRect);
    observer.observe(resolvedTarget.element);
    window.addEventListener('resize', updateRect);
    window.addEventListener('scroll', updateRect, true);

    return () => {
      observer.disconnect();
      window.removeEventListener('resize', updateRect);
      window.removeEventListener('scroll', updateRect, true);
    };
  }, [isActive, resolvedTarget?.element]);

  useEffect(() => {
    if (!currentStep || !isActive) return;
    if (lastViewedStepRef.current === currentStep.id) return;
    lastViewedStepRef.current = currentStep.id;
    trackEvent('tour_step_viewed', {
      tour_id: tour.id,
      step_id: currentStep.id,
      route: location.pathname,
      target_id: currentStep.targetId,
    });
  }, [currentStep, isActive, location.pathname, tour.id]);

  useEffect(() => {
    if (!isActive || !currentStep || currentStep.nextMode !== 'target_click' || !resolvedTarget?.element) {
      return;
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (!target || !resolvedTarget.element.contains(target)) {
        return;
      }

      trackEvent('tour_target_clicked', {
        tour_id: tour.id,
        step_id: currentStep.id,
        route: location.pathname,
        target_id: currentStep.targetId,
      });

      window.setTimeout(() => {
        nextStep();
      }, 0);
    };

    document.addEventListener('click', handleClick, true);
    return () => {
      document.removeEventListener('click', handleClick, true);
    };
  }, [currentStep, isActive, location.pathname, nextStep, resolvedTarget?.element, tour.id]);

  const value = useMemo<ProductTourContextValue>(() => ({
    tourId: tour.id,
    isEnabled: enabled,
    isEligible: eligible,
    isActive,
    currentStep,
    currentStepIndex,
    totalSteps: tour.steps.length,
    targetElement: resolvedTarget?.element ?? null,
    targetRect: resolvedTarget?.rect ?? null,
    startTour,
    restartTour,
    nextStep,
    previousStep,
    skipTour,
    finishTour,
  }), [currentStep, currentStepIndex, eligible, enabled, finishTour, isActive, nextStep, previousStep, resolvedTarget?.element, resolvedTarget?.rect, restartTour, skipTour, startTour, tour.id, tour.steps.length]);

  return (
    <ProductTourContext.Provider value={value}>
      {children}
    </ProductTourContext.Provider>
  );
}

export function useProductTourContext(): ProductTourContextValue {
  const context = useContext(ProductTourContext);
  if (!context) {
    throw new Error('useProductTourContext must be used within ProductTourProvider');
  }
  return context;
}
