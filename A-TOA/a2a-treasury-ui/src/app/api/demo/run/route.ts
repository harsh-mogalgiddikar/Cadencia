import { NextRequest } from "next/server";
import { cookies } from "next/headers";

export const runtime = "nodejs"; // SSE requires Node runtime, not Edge

export async function GET(req: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("a2a_token")?.value;

  const API = process.env.API_BASE_URL ?? "http://localhost:8000";
  const url = new URL(`${API}/v1/demo/run`);

  // Forward any query params (live_mode, buyer_wallet, etc.)
  req.nextUrl.searchParams.forEach((v, k) => url.searchParams.set(k, v));

  const upstream = await fetch(url.toString(), {
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    signal: req.signal,
  });

  // Pass SSE stream directly to browser
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
