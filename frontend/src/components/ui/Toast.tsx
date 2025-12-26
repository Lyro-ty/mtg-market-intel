'use client';

import { useEffect, useState } from 'react';
import type { Toast, ToastType } from '@/contexts/ToastContext';

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const TOAST_ICONS: Record<ToastType, string> = {
  success: 'M5 13l4 4L19 7',
  error: 'M6 18L18 6M6 6l12 12',
  warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
  info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
};

const TOAST_STYLES: Record<ToastType, { bg: string; border: string; icon: string }> = {
  success: {
    bg: 'bg-green-900/90',
    border: 'border-green-500/50',
    icon: 'text-green-400',
  },
  error: {
    bg: 'bg-red-900/90',
    border: 'border-red-500/50',
    icon: 'text-red-400',
  },
  warning: {
    bg: 'bg-amber-900/90',
    border: 'border-amber-500/50',
    icon: 'text-amber-400',
  },
  info: {
    bg: 'bg-accent/20',
    border: 'border-accent/50',
    icon: 'text-accent',
  },
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const styles = TOAST_STYLES[toast.type];

  useEffect(() => {
    // Trigger enter animation
    const enterTimer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(enterTimer);
  }, []);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => onDismiss(toast.id), 200);
  };

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-lg border backdrop-blur-sm shadow-lg
        ${styles.bg} ${styles.border}
        transition-all duration-200 ease-out
        ${isVisible && !isExiting ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'}
        min-w-[280px] max-w-[400px]
      `}
      role="alert"
      aria-live={toast.type === 'error' ? 'assertive' : 'polite'}
    >
      {/* Icon */}
      <div className={`flex-shrink-0 ${styles.icon}`}>
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={TOAST_ICONS[toast.type]} />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{toast.message}</p>
        {toast.description && (
          <p className="mt-1 text-sm text-white/70">{toast.description}</p>
        )}
      </div>

      {/* Dismiss button */}
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 text-white/50 hover:text-white transition-colors p-1 -m-1 rounded hover:bg-white/10"
        aria-label="Dismiss notification"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div
      className={`
        fixed z-50 flex flex-col gap-2
        bottom-4 right-4 sm:right-6
        max-sm:left-4 max-sm:right-4 max-sm:items-center
        pointer-events-none
      `}
      aria-label="Notifications"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <ToastItem toast={toast} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
}

export default ToastContainer;
