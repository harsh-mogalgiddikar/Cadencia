/**
 * Tests for the universal API proxy route at /api/v1/[...path]
 *
 * The proxy reads the a2a_token cookie and forwards requests
 * to the FastAPI backend at API_BASE_URL/v1/<path>.
 */

// We need to mock cookies() before importing the route handlers
const mockCookiesGet = jest.fn().mockReturnValue({ value: "mock_jwt_token" });
jest.mock("next/headers", () => ({
  cookies: () =>
    Promise.resolve({
      get: mockCookiesGet,
      set: jest.fn(),
      delete: jest.fn(),
    }),
}));

import { NextRequest } from "next/server";

// We need to dynamically import because the route relies on next/headers
let GET: typeof import("@/app/api/v1/[...path]/route").GET;
let POST: typeof import("@/app/api/v1/[...path]/route").POST;

beforeAll(async () => {
  process.env.API_BASE_URL = "http://localhost:8000";
  const mod = await import("@/app/api/v1/[...path]/route");
  GET = mod.GET;
  POST = mod.POST;
});

describe("Universal API Proxy", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCookiesGet.mockReturnValue({ value: "mock_jwt_token" });
    global.fetch = jest.fn().mockResolvedValue({
      json: async () => ({ data: "mock" }),
      text: async () => '{"data":"mock"}',
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
    });
  });

  it("forwards GET request to FastAPI with correct URL", async () => {
    const req = new NextRequest("http://localhost:3000/api/v1/sessions");
    await GET(req, { params: Promise.resolve({ path: ["sessions"] }) });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/v1/sessions",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("includes Authorization Bearer token header when cookie exists", async () => {
    const req = new NextRequest("http://localhost:3000/api/v1/sessions");
    await GET(req, { params: Promise.resolve({ path: ["sessions"] }) });
    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer mock_jwt_token",
        }),
      })
    );
  });

  it("forwards query parameters correctly", async () => {
    const req = new NextRequest(
      "http://localhost:3000/api/v1/agents?service=cotton&protocol=DANP-v1"
    );
    await GET(req, { params: Promise.resolve({ path: ["agents"] }) });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/v1/agents?service=cotton&protocol=DANP-v1",
      expect.any(Object)
    );
  });

  it("joins nested path segments correctly", async () => {
    const req = new NextRequest(
      "http://localhost:3000/api/v1/sessions/sess-001/status"
    );
    await GET(req, {
      params: Promise.resolve({ path: ["sessions", "sess-001", "status"] }),
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/v1/sessions/sess-001/status",
      expect.any(Object)
    );
  });

  it("forwards POST request with body", async () => {
    const body = JSON.stringify({ initial_offer_value: 85000 });
    const req = new NextRequest("http://localhost:3000/api/v1/sessions/", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/json" },
    });
    await POST(req, { params: Promise.resolve({ path: ["sessions", ""] }) });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("http://localhost:8000/v1/sessions/"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("returns 502 when backend is unreachable", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    const req = new NextRequest("http://localhost:3000/api/v1/sessions");
    const res = await GET(req, {
      params: Promise.resolve({ path: ["sessions"] }),
    });
    expect(res.status).toBe(502);
    const data = await res.json();
    expect(data.error).toBe("Backend unreachable");
  });

  it("does not include Authorization header when no cookie", async () => {
    mockCookiesGet.mockReturnValue(undefined);
    const req = new NextRequest("http://localhost:3000/api/v1/sessions");
    await GET(req, { params: Promise.resolve({ path: ["sessions"] }) });

    const fetchCall = (fetch as jest.Mock).mock.calls[0];
    const headers = fetchCall[1].headers;
    expect(headers.Authorization).toBeUndefined();
  });
});
