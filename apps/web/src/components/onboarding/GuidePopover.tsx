import { forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/Button';
import { cn } from '../../lib/utils';
import type { ProductTourPlacement, ProductTourStep } from '../../config/productTours/dashboardFirstRun';

export const GuidePopover = forwardRef<HTMLDivElement, {
  step: ProductTourStep;
  currentStepIndex: number;
  totalSteps: number;
  isMobile: boolean;
  placement?: ProductTourPlacement;
  onPrimaryAction: () => void;
  onSkip: () => void;
}>(({ step, currentStepIndex, totalSteps, isMobile, placement = 'bottom', onPrimaryAction, onSkip }, ref) => {
  const { t } = useTranslation('dashboard');
  const title = step.titleKey ? t(step.titleKey, { defaultValue: step.defaultTitle }) : step.defaultTitle;
  const description = step.descriptionKey ? t(step.descriptionKey, { defaultValue: step.defaultDescription }) : step.defaultDescription;
  const ctaLabel = step.ctaLabelKey ? t(step.ctaLabelKey, { defaultValue: step.defaultCtaLabel }) : step.defaultCtaLabel;
  const skipLabel = t('dashboardTour.common.skip', { defaultValue: '跳过引导' });
  const progressLabel = t('dashboardTour.common.progress', {
    current: currentStepIndex + 1,
    total: totalSteps,
    defaultValue: `${currentStepIndex + 1} / ${totalSteps}`,
  });

  return (
    <div
      ref={ref}
      className={cn(
        'pointer-events-auto rounded-[22px] border border-white/12 bg-[linear-gradient(180deg,hsl(var(--bg-secondary))_0%,hsl(var(--bg-secondary)/0.985)_100%)] shadow-[0_20px_48px_hsl(0_0%_0%_/_0.26)] backdrop-blur-xl',
        isMobile ? 'w-[calc(100vw-2rem)] max-w-none p-4' : 'w-80 p-4',
      )}
      role="dialog"
      aria-modal="false"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="rounded-full bg-[hsl(var(--bg-primary)/0.72)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.08em] text-[hsl(var(--text-tertiary))]">
          {progressLabel}
        </div>
        <button
          type="button"
          onClick={onSkip}
          className="text-xs text-[hsl(var(--text-secondary))] transition-colors hover:text-[hsl(var(--text-primary))]"
        >
          {skipLabel}
        </button>
      </div>

      <div className="space-y-2">
        <h3 className="text-[17px] font-semibold tracking-[-0.02em] text-[hsl(var(--text-primary))]">{title}</h3>
        <p className="text-sm leading-6 text-[hsl(var(--text-secondary))]">{description}</p>
      </div>

      <div className="mt-5 flex items-center justify-end">
        <Button size="sm" onClick={onPrimaryAction}>
          {ctaLabel}
        </Button>
      </div>

      {!isMobile && placement !== 'center' && (
        <span
          aria-hidden="true"
          className={cn(
            'absolute h-3.5 w-3.5 rotate-45 border border-white/10 bg-[hsl(var(--bg-secondary))]',
            placement === 'top' && 'left-8 -bottom-1.5 border-l-0 border-t-0',
            placement === 'bottom' && 'left-8 -top-1.5 border-r-0 border-b-0',
            placement === 'left' && 'top-8 -right-1.5 border-l-0 border-b-0',
            placement === 'right' && 'top-8 -left-1.5 border-r-0 border-t-0',
          )}
        />
      )}
    </div>
  );
});

GuidePopover.displayName = 'GuidePopover';
