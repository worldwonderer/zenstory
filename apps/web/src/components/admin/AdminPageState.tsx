import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface AdminPageStateProps {
  isLoading?: boolean;
  isFetching?: boolean;
  isError?: boolean;
  isEmpty?: boolean;
  loadingText?: string;
  errorText?: string;
  emptyText?: string;
  retryText?: string;
  onRetry?: () => void;
  stateClassName?: string;
  children: ReactNode;
}

const DEFAULT_STATE_CLASS =
  "admin-surface flex min-h-[220px] items-center justify-center px-4 py-12";

export function AdminPageState({
  isLoading = false,
  isFetching = false,
  isError = false,
  isEmpty = false,
  loadingText = "Loading...",
  errorText = "Failed to load data",
  emptyText = "No data",
  retryText = "Retry",
  onRetry,
  stateClassName = DEFAULT_STATE_CLASS,
  children,
}: AdminPageStateProps) {
  if (isLoading || (isFetching && isEmpty)) {
    return (
      <div className={stateClassName}>
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-[hsl(var(--accent-primary))]" />
          <div className="text-[hsl(var(--text-secondary))]">{loadingText}</div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className={stateClassName}>
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="text-[hsl(var(--error))]">{errorText}</div>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-[hsl(var(--separator-color))] px-3 py-1.5 text-sm text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
            >
              {retryText}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className={stateClassName}>
        <div className="text-[hsl(var(--text-secondary))]">{emptyText}</div>
      </div>
    );
  }

  return <>{children}</>;
}
