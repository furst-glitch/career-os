// Sentry server instrumentation — loaded by @sentry/nextjs when installed.
export {};

declare const process: { env: Record<string, string | undefined>; };

const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN;
if (dsn) {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const Sentry = require("@sentry/nextjs") as Record<string, (...a: unknown[]) => unknown>;
  Sentry["init"]?.({ dsn, tracesSampleRate: 0.1, environment: process.env.NODE_ENV });
}
