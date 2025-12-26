'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useState, ReactNode } from 'react';

interface PageTransitionProps {
  children: ReactNode;
}

/**
 * PageTransition component provides smooth page transitions.
 *
 * Enter animation: Fade in (150ms) + slide up (8px)
 * Exit animation: Fade out (100ms)
 *
 * Respects prefers-reduced-motion for accessibility.
 */
export function PageTransition({ children }: PageTransitionProps) {
  const pathname = usePathname();
  const [isVisible, setIsVisible] = useState(false);
  const [displayChildren, setDisplayChildren] = useState(children);

  useEffect(() => {
    // Start exit animation
    setIsVisible(false);

    // After exit animation (100ms), update content and trigger enter animation
    const timeout = setTimeout(() => {
      setDisplayChildren(children);
      setIsVisible(true);
    }, 100);

    return () => clearTimeout(timeout);
  }, [pathname, children]);

  return (
    <div
      className={`transition-all duration-150 motion-reduce:transition-none ${
        isVisible
          ? 'opacity-100 translate-y-0'
          : 'opacity-0 translate-y-2'
      }`}
    >
      {displayChildren}
    </div>
  );
}
