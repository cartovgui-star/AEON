import { useEffect, useRef, useCallback } from 'react';

/**
 * Unified auto-refresh hook.
 * Calls `callback` immediately on mount, then every `intervalMs` ms.
 * Cleans up on unmount. Changing `intervalMs` restarts the timer.
 *
 * Usage:
 *   useAutoRefresh(fetchData, 15000);   // refresh every 15s
 *   useAutoRefresh(fetchData);           // default 10s
 */
export function useAutoRefresh(callback, intervalMs = 10000) {
  const saved = useRef(callback);

  // Keep ref up-to-date without restarting the interval
  useEffect(() => {
    saved.current = callback;
  }, [callback]);

  useEffect(() => {
    // Fire immediately
    saved.current();
    const id = setInterval(() => saved.current(), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}
