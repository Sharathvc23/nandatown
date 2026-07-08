import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Clears the session cookie. POST-only so a stray <img> tag can't log people out. */
export async function POST(req: NextRequest) {
  const origin = req.headers.get("origin");
  if (origin) {
    try {
      if (new URL(origin).host !== req.nextUrl.host) {
        return NextResponse.json({ error: "Bad origin" }, { status: 403 });
      }
    } catch {
      return NextResponse.json({ error: "Bad origin" }, { status: 403 });
    }
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
