// Conditionally load Sentry - only if the package is installed
let withSentryConfig;
try {
  withSentryConfig = require('@sentry/nextjs').withSentryConfig;
} catch {
  // Sentry not installed, will use plain nextConfig
  withSentryConfig = null;
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cards.scryfall.io',
      },
      {
        protocol: 'https',
        hostname: 'c1.scryfall.com',
      },
    ],
  },
  async rewrites() {
    // For Docker production builds, always use the backend service name
    // The BACKEND_URL build arg should be set, but we default to the service name
    // This is evaluated at build time for standalone output
    const backendUrl = process.env.BACKEND_URL || 'http://backend:8000';

    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

// Only wrap with Sentry if DSN is configured
const sentryWebpackPluginOptions = {
  // Suppress source map upload errors in development
  silent: true,
  // Don't upload source maps if no auth token
  dryRun: !process.env.SENTRY_AUTH_TOKEN,
};

// Only wrap with Sentry if DSN is configured AND package is installed
module.exports = (process.env.NEXT_PUBLIC_SENTRY_DSN && withSentryConfig)
  ? withSentryConfig(nextConfig, sentryWebpackPluginOptions)
  : nextConfig;

