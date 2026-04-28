import { useState, useEffect, useRef } from 'react';

interface UseDelayedLoadingOptions {
  /** 多少毫秒后显示 loading（默认 200ms） */
  delay?: number;
  /** loading 最少显示多少毫秒（默认 400ms） */
  minDuration?: number;
}

/**
 * 延迟显示 loading 状态的 hook
 * - 如果 isLoading 在 delay 时间内变为 false，不显示 loading
 * - 如果显示了 loading，至少显示 minDuration 毫秒
 */
export function useDelayedLoading(
  isLoading: boolean,
  options: UseDelayedLoadingOptions = {}
): boolean {
  const { delay = 200, minDuration = 400 } = options;
  const [showLoader, setShowLoader] = useState(false);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (isLoading && !startTimeRef.current) {
      // 开始加载，记录开始时间
      startTimeRef.current = Date.now();

      // 延迟显示 loader
      const timer = setTimeout(() => setShowLoader(true), delay);
      return () => clearTimeout(timer);
    }

    if (!isLoading && startTimeRef.current) {
      // 加载结束
      const elapsed = Date.now() - startTimeRef.current;

      if (showLoader) {
        // 如果已经显示了 loader，确保最少显示时间
        const remaining = Math.max(0, minDuration - elapsed);
        const timer = setTimeout(() => {
          setShowLoader(false);
          startTimeRef.current = null;
        }, remaining);
        return () => clearTimeout(timer);
      } else {
        // 还没显示 loader，直接重置
        startTimeRef.current = null;
      }
    }
  }, [isLoading, showLoader, delay, minDuration]);

  return showLoader;
}

export default useDelayedLoading;
