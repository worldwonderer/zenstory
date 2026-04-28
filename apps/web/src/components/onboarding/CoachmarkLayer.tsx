import { createPortal } from 'react-dom';
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useIsMobile, useIsTablet } from '../../hooks/useMediaQuery';
import { getCoachmarkPosition, getSpotlightRect } from '../../lib/productTourPositioning';
import { GuidePopover } from './GuidePopover';
import { SpotlightMask } from './SpotlightMask';
import { useProductTour } from '../../hooks/useProductTour';

const DEFAULT_POPOVER_SIZE = { width: 320, height: 186 };

export function CoachmarkLayer() {
  const {
    isActive,
    currentStep,
    currentStepIndex,
    totalSteps,
    targetElement,
    targetRect,
    nextStep,
    skipTour,
  } = useProductTour();
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [popoverSize, setPopoverSize] = useState(DEFAULT_POPOVER_SIZE);

  useLayoutEffect(() => {
    if (!popoverRef.current) return;
    const rect = popoverRef.current.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    setPopoverSize({ width: rect.width, height: rect.height });
  }, [currentStep?.id, isMobile, isTablet, targetRect?.height, targetRect?.left, targetRect?.top, targetRect?.width]);

  const spotlightRect = useMemo(
    () => (
      targetRect && currentStep
        ? getSpotlightRect(
            targetRect,
            isMobile
              ? (currentStep.mobileSpotlightPadding ?? currentStep.spotlightPadding ?? 12)
              : (currentStep.spotlightPadding ?? 12),
            isMobile
              ? (currentStep.mobileSpotlightOffsetX ?? currentStep.spotlightOffsetX ?? 0)
              : (currentStep.spotlightOffsetX ?? 0),
            isMobile
              ? (currentStep.mobileSpotlightOffsetY ?? currentStep.spotlightOffsetY ?? 0)
              : (currentStep.spotlightOffsetY ?? 0),
          )
        : null
    ),
    [currentStep, isMobile, targetRect],
  );

  const position = useMemo(() => {
    if (!targetRect || !currentStep || isMobile) return null;
    return getCoachmarkPosition({
      targetRect,
      popoverSize,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      placement: currentStep.placement,
    });
  }, [currentStep, isMobile, popoverSize, targetRect]);

  if (!isActive || !currentStep || !targetRect || typeof document === 'undefined') {
    return null;
  }

  const handlePrimaryAction = () => {
    if (currentStep.nextMode === 'target_click' && targetElement) {
      targetElement.click();
      return;
    }
    nextStep();
  };

  return createPortal(
    <>
      <SpotlightMask rect={spotlightRect} />
      <div className="pointer-events-none fixed inset-0 z-[1305]">
        <div
          className={isMobile ? 'absolute inset-x-4 bottom-4' : 'absolute'}
          style={
            position
              ? {
                  top: position.top,
                  left: position.left,
                }
              : undefined
          }
        >
          <GuidePopover
            ref={popoverRef}
            step={currentStep}
            currentStepIndex={currentStepIndex}
            totalSteps={totalSteps}
            isMobile={isMobile}
            placement={position?.placement ?? currentStep.placement}
            onPrimaryAction={handlePrimaryAction}
            onSkip={skipTour}
          />
        </div>
      </div>
    </>,
    document.body,
  );
}

export default CoachmarkLayer;
