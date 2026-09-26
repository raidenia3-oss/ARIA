import { NextResponse } from "next/server";
import { NextRequest } from "next/server";

const getIP = (request: NextRequest) => {
  const xForwardedFor = request.headers.get("x-forwarded-for");
  if (xForwardedFor) {
    return xForwardedFor.split(",").shift();
  }
  return request.headers.get("x-real-ip");
};

const rateLimit = (limit: number, windowMs: number) => {
  const tokens = new Map<string, number>();
  const lastReset = new Map<string, number>();

  return (request: NextRequest, res: typeof NextResponse) => {
    const ip = getIP(request);
    if (!ip) {
      return res.json({ error: "Missing IP address" }, { status: 400 });
    }

    const now = Date.now();
    const last = lastReset.get(ip) || 0;

    if (now - last > windowMs) {
      tokens.set(ip, limit - 1);
      lastReset.set(ip, now);
    } else {
      const currentTokens = tokens.get(ip) || 0;
      if (currentTokens > 0) {
        tokens.set(ip, currentTokens - 1);
      } else {
        return res.json({ error: "Too Many Requests" }, { status: 429 });
      }
    }
    return true;
  };
};

export default rateLimit;