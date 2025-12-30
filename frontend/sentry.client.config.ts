// This file configures the initialization of Sentry on the client.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (SENTRY_DSN) {
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: process.env.NODE_ENV,

    // Performance Monitoring
    tracesSampleRate: 0.1, // 10% of transactions

    // Session Replay (disabled for now - can enable later)
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,

    // Don't send errors in development
    enabled: process.env.NODE_ENV === 'production',

    // Ignore common non-actionable errors
    ignoreErrors: [
      // Network errors
      'Failed to fetch',
      'NetworkError',
      'Load failed',
      // User navigation
      'AbortError',
      'cancelled',
      // Browser extensions
      /^chrome-extension:/,
      /^moz-extension:/,
    ],
  });
}
