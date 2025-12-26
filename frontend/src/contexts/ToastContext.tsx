'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { ToastContainer } from '@/components/ui/Toast';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  description?: string;
}

interface ToastContextType {
  toasts: Toast[];
  toast: {
    success: (message: string, options?: { description?: string }) => void;
    error: (message: string, options?: { description?: string }) => void;
    warning: (message: string, options?: { description?: string }) => void;
    info: (message: string, options?: { description?: string }) => void;
  };
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((type: ToastType, message: string, options?: { description?: string }) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newToast: Toast = { id, type, message, description: options?.description };

    setToasts((prev) => [...prev.slice(-2), newToast]); // Keep max 3

    if (type !== 'error') {
      setTimeout(() => dismiss(id), 4000);
    }
  }, [dismiss]);

  const toast = {
    success: (message: string, options?: { description?: string }) => addToast('success', message, options),
    error: (message: string, options?: { description?: string }) => addToast('error', message, options),
    warning: (message: string, options?: { description?: string }) => addToast('warning', message, options),
    info: (message: string, options?: { description?: string }) => addToast('info', message, options),
  };

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}

export type { Toast, ToastType, ToastContextType };
