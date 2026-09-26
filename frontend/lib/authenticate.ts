import { NextRequest, NextResponse } from "next/server";

export const authenticate = (request: NextRequest) => {
  const authHeader = request.headers.get("authorization");

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const token = authHeader.split(" ")[1];

  if (token !== process.env.API_SECRET_KEY) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return null; // Authentication successful
};
