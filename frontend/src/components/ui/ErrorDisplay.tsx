/**
 * Standardized error display component for API errors.
 * 
 * Provides consistent error messaging across the application.
 */
'use client';

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';
import { Card, CardContent } from './Card';

interface ErrorDisplayProps {
  /** Error message to display */
  message?: string;
  /** HTTP status code if available */
  status?: number;
  /** Callback to retry the operation */
  onRetry?: () => void;
  /** Whether to show retry button */
  showRetry?: boolean;
  /** Additional context or details */
  details?: string;
  /** Custom title */
  title?: string;
}

export function ErrorDisplay({
  message = 'An error occurred',
  status,
  onRetry,
  showRetry = true,
  details,
  title = 'Error',
}: ErrorDisplayProps) {
  // Format status code message
  const getStatusMessage = (code?: number): string => {
    if (!code) return '';
    
    const statusMessages: Record<number, string> = {
      400: 'Bad Request',
      401: 'Authentication Required',
      403: 'Access Denied',
      404: 'Not Found',
      408: 'Request Timeout',
      429: 'Too Many Requests',
      500: 'Server Error',
      502: 'Bad Gateway',
      503: 'Service Unavailable',
    };
    
    return statusMessages[code] || `HTTP ${code}`;
  };

  const statusMessage = getStatusMessage(status);

  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          <AlertTriangle className="h-6 w-6 text-red-500 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-[rgb(var(--foreground))] mb-1">
              {title}
            </h3>
            <p className="text-[rgb(var(--muted-foreground))] mb-2">
              {message}
            </p>
            {statusMessage && (
              <p className="text-sm text-[rgb(var(--muted-foreground))] mb-2">
                {statusMessage}
              </p>
            )}
            {details && (
              <p className="text-sm text-[rgb(var(--muted-foreground))] mb-4">
                {details}
              </p>
            )}
            {showRetry && onRetry && (
              <Button
                onClick={onRetry}
                variant="outline"
                size="sm"
                className="mt-2"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Inline error display for smaller errors (e.g., in forms).
 */
export function InlineError({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 text-red-500 text-sm mt-1">
      <AlertTriangle className="h-4 w-4" />
      <span>{message}</span>
    </div>
  );
}

