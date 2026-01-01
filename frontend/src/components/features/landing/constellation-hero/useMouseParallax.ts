'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { MousePosition } from './types';

interface UseMouseParallaxOptions {
  /** Throttle interval in ms (default: 16 for ~60fps) */
  throttleMs?: number;
  /** Whether to track mouse (disable on mobile) */
  enabled?: boolean;
}

export function useMouseParallax(options: UseMouseParallaxOptions = {}) {
  const { throttleMs = 16, enabled = true } = options;

  const [mousePosition, setMousePosition] = useState<MousePosition>({ x: 0.5, y: 0.5 });
  const containerRef = useRef<HTMLDivElement>(null);
  const lastUpdateRef = useRef<number>(0);
  const rafRef = useRef<number | null>(null);

  const handleMouseMove = useCallback((event: MouseEvent) => {
    if (!enabled) return;

    const now = Date.now();
    if (now - lastUpdateRef.current < throttleMs) return;
    lastUpdateRef.current = now;

    // Cancel any pending RAF
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    rafRef.current = requestAnimationFrame(() => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;

      // Clamp to 0-1 range
      setMousePosition({
        x: Math.max(0, Math.min(1, x)),
        y: Math.max(0, Math.min(1, y)),
      });
    });
  }, [enabled, throttleMs]);

  const handleMouseLeave = useCallback(() => {
    // Smoothly return to center when mouse leaves
    setMousePosition({ x: 0.5, y: 0.5 });
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !enabled) return;

    container.addEventListener('mousemove', handleMouseMove);
    container.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      container.removeEventListener('mousemove', handleMouseMove);
      container.removeEventListener('mouseleave', handleMouseLeave);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [handleMouseMove, handleMouseLeave, enabled]);

  return { mousePosition, containerRef };
}
