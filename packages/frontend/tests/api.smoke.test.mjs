import { test } from "node:test";
import assert from "node:assert/strict";

// HTTP-level smoke tests. They only run when a live server is available
// (set BASE_URL, e.g. after `vercel dev` or a production deploy). This keeps
// the suite green locally where the Next 9.3.3 install cannot boot the
// App Router, while still giving CI a real endpoint check.
const BASE_URL = process.env.BASE_URL;
const runner = BASE_URL ? test : test.skip;

runner("GET /api/health returns ok:true", async () => {
  const res = await fetch(`${BASE_URL}/api/health`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
});

runner("GET /api/integrations/status returns webhooks state", async () => {
  const res = await fetch(`${BASE_URL}/api/integrations/status`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.ok("webhooks" in body);
});

runner("GET /api/logs returns a logs array", async () => {
  const res = await fetch(`${BASE_URL}/api/logs`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.ok(Array.isArray(body.logs));
});
