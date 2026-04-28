import { Sparkles } from "lucide-react";
import { cn } from "../../lib/utils";

export interface ComingSoonStateProps {
  title: string;
  description: string;
  compact?: boolean;
  className?: string;
}

export function ComingSoonState({
  title,
  description,
  compact = false,
  className,
}: ComingSoonStateProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-dashed border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] text-center",
        compact ? "px-4 py-6" : "px-6 py-12",
        className
      )}
      data-testid="coming-soon-state"
    >
      <div
        className={cn(
          "mx-auto mb-3 rounded-xl bg-[hsl(var(--accent-primary)/0.12)] text-[hsl(var(--accent-primary))] flex items-center justify-center",
          compact ? "w-10 h-10" : "w-12 h-12"
        )}
      >
        <Sparkles className={compact ? "w-5 h-5" : "w-6 h-6"} />
      </div>
      <h3
        className={cn(
          "font-semibold text-[hsl(var(--text-primary))] mb-2",
          compact ? "text-base" : "text-xl"
        )}
      >
        {title}
      </h3>
      <p
        className={cn(
          "text-[hsl(var(--text-secondary))] mx-auto",
          compact ? "text-xs max-w-[260px]" : "text-base max-w-xl"
        )}
      >
        {description}
      </p>
    </div>
  );
}
