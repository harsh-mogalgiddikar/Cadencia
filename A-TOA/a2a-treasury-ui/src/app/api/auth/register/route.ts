import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // Step 1: Register the enterprise via POST /v1/enterprises/register
    const registerRes = await fetch(
      `${process.env.API_BASE_URL}/v1/enterprises/register`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          legal_name: body.legal_name,
          pan: body.pan_number || undefined,
          gst: body.gst_number || undefined,
          email: body.email,
          password: body.password,
          wallet_address: body.wallet_address || undefined,
        }),
      }
    );

    if (!registerRes.ok) {
      const error = await registerRes.json();

      // Map common conflict errors to user-friendly messages
      if (registerRes.status === 409) {
        const detail =
          typeof error.detail === "string" ? error.detail : "";
        if (detail.toLowerCase().includes("email")) {
          return NextResponse.json(
            { detail: "An enterprise with this email already exists." },
            { status: 409 }
          );
        }
        if (detail.toLowerCase().includes("pan")) {
          return NextResponse.json(
            { detail: "An enterprise with this PAN number already exists." },
            { status: 409 }
          );
        }
        if (detail.toLowerCase().includes("gst")) {
          return NextResponse.json(
            { detail: "An enterprise with this GST number already exists." },
            { status: 409 }
          );
        }
        return NextResponse.json(
          {
            detail:
              detail || "An enterprise with these details already exists.",
          },
          { status: 409 }
        );
      }

      return NextResponse.json(error, { status: registerRes.status });
    }

    // Step 2: Auto-login after successful registration
    const loginRes = await fetch(
      `${process.env.API_BASE_URL}/v1/auth/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: body.email, password: body.password }),
      }
    );

    if (!loginRes.ok) {
      // Registration succeeded but auto-login failed — still redirect to login
      return NextResponse.json(
        { success: true, autoLogin: false },
        { status: 201 }
      );
    }

    const { access_token } = await loginRes.json();

    // Set httpOnly cookie
    const cookieStore = await cookies();
    cookieStore.set("a2a_token", access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24,
      path: "/",
    });

    return NextResponse.json({ success: true, autoLogin: true });
  } catch {
    return NextResponse.json(
      { detail: "Failed to connect to registration service" },
      { status: 502 }
    );
  }
}
