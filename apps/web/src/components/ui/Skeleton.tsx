import React from "react";
import { cn } from "../../lib/utils";

export interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular" | "card";
  width?: string | number;
  height?: string | number;
  animation?: "pulse" | "shimmer" | "none";
}

/**
 * A skeleton loading component for displaying placeholder content.
 * Supports multiple variants and animation styles.
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  className = "",
  variant = "text",
  width,
  height,
  animation = "pulse",
}) => {
  const baseStyles = "bg-[hsl(var(--bg-tertiary))]";

  const variantStyles: Record<string, string> = {
    text: "h-4 rounded",
    circular: "rounded-full aspect-square",
    rectangular: "rounded-lg",
    card: "rounded-lg",
  };

  const animationStyles: Record<string, string> = {
    pulse: "animate-pulse",
    shimmer: "skeleton-shimmer",
    none: "",
  };

  const style: React.CSSProperties = {
    width: width !== undefined ? (typeof width === "number" ? `${width}px` : width) : undefined,
    height: height !== undefined ? (typeof height === "number" ? `${height}px` : height) : undefined,
  };

  return (
    <div
      className={cn(
        baseStyles,
        variantStyles[variant],
        animationStyles[animation],
        className
      )}
      style={style}
      role="status"
      aria-label="Loading..."
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
};

// Preset components for common use cases

interface CardSkeletonProps {
  className?: string;
  showHeader?: boolean;
  showFooter?: boolean;
  lines?: number;
}

/**
 * Card skeleton for loading card content.
 */
export const CardSkeleton: React.FC<CardSkeletonProps> = ({
  className = "",
  showHeader = true,
  showFooter = false,
  lines = 3,
}) => {
  return (
    <div
      className={cn(
        "bg-[hsl(var(--bg-secondary))] rounded-xl p-4 space-y-3",
        className
      )}
      role="status"
      aria-label="Loading card..."
    >
      {showHeader && (
        <div className="flex items-center gap-3">
          <Skeleton variant="circular" width={40} height={40} />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width="60%" />
            <Skeleton variant="text" width="40%" height={12} />
          </div>
        </div>
      )}
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            variant="text"
            width={i === lines - 1 ? "80%" : "100%"}
          />
        ))}
      </div>
      {showFooter && (
        <div className="flex gap-2 pt-2">
          <Skeleton variant="rectangular" width={80} height={32} />
          <Skeleton variant="rectangular" width={80} height={32} />
        </div>
      )}
      <span className="sr-only">Loading card...</span>
    </div>
  );
};

interface AvatarSkeletonProps {
  className?: string;
  size?: number | string;
}

/**
 * Avatar skeleton for loading avatar placeholders.
 */
export const AvatarSkeleton: React.FC<AvatarSkeletonProps> = ({
  className = "",
  size = 40,
}) => {
  return (
    <Skeleton
      variant="circular"
      width={size}
      height={size}
      className={className}
    />
  );
};

interface TableRowSkeletonProps {
  className?: string;
  columns?: number;
  rows?: number;
}

/**
 * Table row skeleton for loading table content.
 */
export const TableRowSkeleton: React.FC<TableRowSkeletonProps> = ({
  className = "",
  columns = 4,
  rows = 5,
}) => {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-label="Loading table...">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex items-center gap-4 py-3 border-b border-[hsl(var(--border-color))]"
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              variant="text"
              width={colIndex === 0 ? 48 : colIndex === columns - 1 ? 80 : "100%"}
              className="flex-1"
            />
          ))}
        </div>
      ))}
      <span className="sr-only">Loading table...</span>
    </div>
  );
};

interface TextSkeletonProps {
  className?: string;
  lines?: number;
  lineHeight?: number | string;
}

/**
 * Multi-line text skeleton for loading text content.
 */
export const TextSkeleton: React.FC<TextSkeletonProps> = ({
  className = "",
  lines = 3,
  lineHeight = 16,
}) => {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-label="Loading text...">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          width={i === lines - 1 ? "75%" : "100%"}
          height={lineHeight}
        />
      ))}
      <span className="sr-only">Loading text...</span>
    </div>
  );
};

export default Skeleton;
