/**
 * Server-side proxy to Echo API.
 *
 * Why: keeps JWT in httpOnly cookie, never exposed to JS. Browser calls
 * /api/echo/v1/quant/earnings; this route forwards with Authorization header.
 */
import { NextRequest, NextResponse } from "next/server";

const ECHO_API_URL = process.env.ECHO_API_URL || "http://localhost:8000";

async function forward(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = "/" + params.path.join("/");
  const url = new URL(req.url);
  const target = `${ECHO_API_URL}${path}${url.search}`;

  // Pull session token from httpOnly cookie
  const session = req.cookies.get("echo_session")?.value;

  const headers = new Headers();
  // Pass through content-type and idempotency-key
  for (const h of ["content-type", "idempotency-key", "x-request-id"]) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }
  if (session) headers.set("authorization", `Bearer ${session}`);

  const init: RequestInit = {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
    // Don't auto-follow; let the client see redirects
    redirect: "manual",
  };

  const upstream = await fetch(target, init);
  const respHeaders = new Headers(upstream.headers);
  // Strip hop-by-hop
  respHeaders.delete("transfer-encoding");
  respHeaders.delete("content-encoding");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: respHeaders,
  });
}

export const GET = forward;
export const POST = forward;
export const DELETE = forward;
export const PATCH = forward;
export const PUT = forward;
