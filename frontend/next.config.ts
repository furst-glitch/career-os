import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.supabase.co",
      },
    ],
  },
};

// Wrap with Sentry only when the package is installed + DSN is configured.
// Safe dynamic require so tsc doesn't fail before npm install.
function withSentryIfAvailable(config: NextConfig): NextConfig {
  if (!process.env.NEXT_PUBLIC_SENTRY_DSN) return config;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { withSentryConfig } = require("@sentry/nextjs") as {
      withSentryConfig: (cfg: NextConfig, opts: Record<string, unknown>) => NextConfig;
    };
    return withSentryConfig(config, {
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      silent: !process.env.CI,
      widenClientFileUpload: true,
      hideSourceMaps: true,
      disableLogger: true,
    });
  } catch {
    return config;
  }
}

export default withSentryIfAvailable(nextConfig);
