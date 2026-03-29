import { cookies } from "next/headers";
import { NextResponse } from "next/server";

/**
 * GET /api/auth/me
 *
 * The backend has no /enterprises/me endpoint.
 * Instead, we decode the JWT to get enterprise_id, then fetch
 * GET /v1/enterprises/{enterprise_id} with the Bearer token.
 */
export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get("a2a_token")?.value;

  if (!token) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    // Decode JWT payload to get enterprise_id (JWT is base64url-encoded)
    const payloadPart = token.split(".")[1];
    if (!payloadPart) {
      cookieStore.delete("a2a_token");
      return NextResponse.json({ error: "Malformed token" }, { status: 401 });
    }

    const decoded = JSON.parse(
      Buffer.from(payloadPart, "base64url").toString("utf-8")
    );
    const enterpriseId = decoded.enterprise_id;
    const role = decoded.role; // "admin", "auditor", etc.

    if (!enterpriseId) {
      cookieStore.delete("a2a_token");
      return NextResponse.json({ error: "Invalid token" }, { status: 401 });
    }

    // Fetch enterprise detail from backend
    const res = await fetch(
      `${process.env.API_BASE_URL}/v1/enterprises/${enterpriseId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    );

    if (!res.ok) {
      if (res.status === 401) {
        cookieStore.delete("a2a_token");
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
      }
      const error = await res.json();
      return NextResponse.json(error, { status: res.status });
    }

    const profile = await res.json();

    // Augment profile with role from JWT (backend Enterprise model doesn't have role)
    return NextResponse.json({
      ...profile,
      role: role === "admin" ? "buyer" : role, // Map admin role to buyer for display
    });
  } catch {
    return NextResponse.json(
      { error: "Failed to fetch profile" },
      { status: 502 }
    );
  }
}
