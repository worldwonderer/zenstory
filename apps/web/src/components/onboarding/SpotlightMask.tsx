import { cn } from '../../lib/utils';
import type { RectLike } from '../../lib/productTourPositioning';

export function SpotlightMask({
  rect,
  className,
}: {
  rect: RectLike | null;
  className?: string;
}) {
  if (!rect) return null;

  return (
    <div className={cn('pointer-events-none fixed inset-0 z-[1300]', className)}>
      <div
        className="absolute rounded-[24px] border border-white/42 bg-white/[0.02] shadow-[0_0_0_9999px_rgba(15,23,42,0.56),0_0_0_1px_rgba(255,255,255,0.05),0_0_18px_rgba(148,163,184,0.08)] ring-1 ring-white/6 transition-all duration-200"
        style={{
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
        }}
      />
    </div>
  );
}

export default SpotlightMask;
