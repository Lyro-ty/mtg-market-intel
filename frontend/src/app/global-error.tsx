'use client';

import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0C0C10] flex items-center justify-center p-4">
        <div className="max-w-md w-full p-8 rounded-lg border border-[#2A2A35] bg-[#14141A] text-center">
          {/* Error Icon */}
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-8 h-8 text-red-500" />
          </div>

          {/* Message */}
          <h1 className="text-2xl font-bold text-white mb-2">Critical Error</h1>
          <p className="text-gray-400 mb-6">
            Something went seriously wrong. Please try refreshing the page.
          </p>

          {/* Error Details */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mb-6 p-3 rounded-lg bg-[#1C1C24] text-left">
              <p className="text-xs text-gray-400 font-mono break-all">
                {error.message}
              </p>
            </div>
          )}

          {/* Actions */}
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-700 text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
