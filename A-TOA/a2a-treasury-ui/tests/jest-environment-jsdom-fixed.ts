/**
 * Custom Jest environment that extends jsdom but preserves Node.js
 * globals needed by MSW v2 (Response, Request, fetch, etc.)
 *
 * Usage in jest.config.ts:
 *   testEnvironment: "./tests/jest-environment-jsdom-fixed.ts"
 */

import JsdomEnvironment from "jest-environment-jsdom";
import type { JestEnvironmentConfig, EnvironmentContext } from "@jest/environment";

export default class JsdomFixedEnvironment extends JsdomEnvironment {
  constructor(config: JestEnvironmentConfig, context: EnvironmentContext) {
    super(config, context);

    // MSW v2 needs these Node.js globals that jsdom doesn't provide
    // Node 18+ has them natively on globalThis
    const globals = [
      "fetch",
      "Headers",
      "Request",
      "Response",
      "ReadableStream",
      "WritableStream",
      "TransformStream",
      "Blob",
      "FormData",
      "File",
      "TextEncoder",
      "TextDecoder",
      "AbortController",
      "AbortSignal",
      "BroadcastChannel",
      "structuredClone",
    ] as const;

    for (const name of globals) {
      if (name in globalThis && !(name in this.global)) {
        // @ts-expect-error - dynamically assigning to global
        this.global[name] = globalThis[name];
      }
    }
  }
}
