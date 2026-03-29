/**
 * Polyfill globals required by MSW v2 in jest-environment-jsdom.
 * jsdom doesn't provide these Web API globals natively.
 */

import { TextDecoder, TextEncoder } from "util";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(global as any).TextEncoder = TextEncoder;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(global as any).TextDecoder = TextDecoder;

// Fetch API globals from Node 18+
const { Response, Request, Headers, fetch } = globalThis;
if (!globalThis.Response) {
  Object.assign(globalThis, { Response, Request, Headers, fetch });
}

// BroadcastChannel polyfill
if (typeof globalThis.BroadcastChannel === "undefined") {
  // @ts-expect-error - minimal polyfill
  globalThis.BroadcastChannel = class {
    name: string;
    constructor(name: string) {
      this.name = name;
    }
    postMessage() {}
    close() {}
    addEventListener() {}
    removeEventListener() {}
  };
}
