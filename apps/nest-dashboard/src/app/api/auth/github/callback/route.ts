import { NextRequest, NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  SESSION_TTL_S,
  STATE_COOKIE,
  baseUrl,
  cookiesSecure,
  decodeStateCookie,
  encodeSession,
} from "@/lib/auth";

export const dynamic = "force-dynamic";

/** Step 2 of GitHub sign-in: exchange the code, set the session cookie. */
export async function GET(req: NextRequest) {
  const clientId = process.env.GITHUB_CLIENT_ID;
  const clientSecret = process.env.GITHUB_CLIENT_SECRET;

  const fail = (code: string) => {
    const res = NextResponse.redirect(
      `${baseUrl()}/skills?auth_error=${code}`,
    );
    res.cookies.set(STATE_COOKIE, "", { path: "/", maxAge: 0 });
    return res;
  };

  if (!clientId || !clientSecret || !process.env.AUTH_SECRET) {
    return fail("not_configured");
  }

  const code = req.nextUrl.searchParams.get("code");
  const state = req.nextUrl.searchParams.get("state");
  const stored = decodeStateCookie(req.cookies.get(STATE_COOKIE)?.value);
  if (!code || !state || !stored || stored.state !== state) {
    return fail("interrupted");
  }

  const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: `${baseUrl()}/api/auth/github/callback`,
    }),
  });
  if (!tokenRes.ok) return fail("rejected");

  const tokens = (await tokenRes.json()) as { access_token?: string };
  if (!tokens.access_token) return fail("no_identity");

  const userRes = await fetch("https://api.github.com/user", {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "nandatown",
    },
  });
  if (!userRes.ok) return fail("no_identity");

  const profile = (await userRes.json()) as {
    id?: number;
    login?: string;
    name?: string | null;
    avatar_url?: string;
  };
  if (!profile.id) return fail("no_identity");

  const session = encodeSession({
    sub: `github:${profile.id}`,
    name: profile.name?.trim() || profile.login || "GitHub user",
    avatar: profile.avatar_url ?? null,
    provider: "github",
  });

  const res = NextResponse.redirect(`${baseUrl()}${stored.next}`);
  res.cookies.set(SESSION_COOKIE, session, {
    httpOnly: true,
    secure: cookiesSecure(),
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_TTL_S,
  });
  res.cookies.set(STATE_COOKIE, "", { path: "/", maxAge: 0 });
  return res;
}
