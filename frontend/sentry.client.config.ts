// Sentry client instrumentation — loaded by @sentry/nextjs when installed.
// This file is intentionally a no-op when @sentry/nextjs is not installed.
export {};

declare const process: { env: Record<string, string | undefined>; };

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Sentry = require("@sentry/nextjs") as Record<string, (...a: unknown[]) => unknown>;
  Sentry["init"]?.({
    dsn,
    tracesSampleRate: 0.2,
    replaysSessionSampleRate: 0.05,
    replaysOnErrorSampleRate: 1.0,
    environment: process.env.NODE_ENV,
    integrations: Sentry["replayIntegration"]
      ? [Sentry["replayIntegration"]({ maskAllText: true, blockAllMedia: true })]
      : [],
  });
}
