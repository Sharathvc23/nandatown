import { NextRequest, NextResponse } from "next/server";
import {
  STATE_COOKIE,
  baseUrl,
  cookiesSecure,
  encodeStateCookie,
  newState,
  safeNextPath,
} from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Step 1 of GitHub sign-in: bounce to GitHub's authorize screen. */
export async function GET(req: NextRequest) {
  const clientId = process.env.GITHUB_CLIENT_ID;
  if (!clientId || !process.env.AUTH_SECRET) {
    return NextResponse.json(
      { error: "GitHub sign-in is not configured on this server." },
      { status: 503 },
    );
  }

  const state = newState();
  const next = safeNextPath(req.nextUrl.searchParams.get("next"));

  const authorize = new URL("https://github.com/login/oauth/authorize");
  authorize.searchParams.set("client_id", clientId);
  authorize.searchParams.set("redirect_uri", `${baseUrl()}/api/auth/github/callback`);
  authorize.searchParams.set("state", state);
  // No scope: public profile (id, login, name, avatar) is all we need.

  const res = NextResponse.redirect(authorize);
  res.cookies.set(STATE_COOKIE, encodeStateCookie(state, next), {
    httpOnly: true,
    secure: cookiesSecure(),
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });
  return res;
}
