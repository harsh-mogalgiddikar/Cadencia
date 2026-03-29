import { NextRequest, NextResponse } from "next/server";

export async function GET(_req: NextRequest) {
  const API = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${API}/v1/demo/mode`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ mode: "SIMULATION", is_live: false });
  }
}
