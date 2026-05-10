import createMiddleware from "next-intl/middleware";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { routing } from "@/i18n/routing";

const intl = createMiddleware(routing);

const PUBLIC_PATHS = ["/auth", "/api/auth"];

export default async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Auth check happens via the session cookie; importing `auth()` here would
  // pull the OIDC provider into the edge runtime. We defer the actual user
  // resolution to server components and just gate the cookie's presence.
  const sessionCookie =
    req.cookies.get("authjs.session-token")?.value ??
    req.cookies.get("__Secure-authjs.session-token")?.value;
  const isLoggedIn = Boolean(sessionCookie);
  const localized = intl(req);

  if (!isLoggedIn && !pathname.startsWith("/auth")) {
    const url = req.nextUrl.clone();
    url.pathname = "/auth/signin";
    url.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(url);
  }

  return localized;
}

export const config = {
  matcher: ["/((?!_next|_vercel|.*\\..*).*)"],
};
