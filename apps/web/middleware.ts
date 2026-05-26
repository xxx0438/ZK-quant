/**
 * Gate /quant/* routes — must have session cookie.
 */
import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;
  if (path.startsWith("/quant/dashboard") || path.startsWith("/quant/earnings")) {
    const session = req.cookies.get("echo_session")?.value;
    if (!session) {
      const url = new URL("/login", req.url);
      url.searchParams.set("returnTo", path);
      return NextResponse.redirect(url);
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/quant/:path*"],
};
