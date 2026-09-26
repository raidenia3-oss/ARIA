import { NextRequest } from "next/server";
import { authenticate } from "./authenticate";

// Returns a NextResponse (401/403) when auth is required and missing/invalid,
// or null when the request is allowed. Auth is only enforced when
// API_SECRET_KEY is configured, so local/dev (no secret) keeps the demo
// endpoints open. This avoids breaking the client dashboard, which has no
// user session to present a bearer token.
export function requireAuth(request: NextRequest) {
  if (!process.env.API_SECRET_KEY) return null;
  return authenticate(request);
}
