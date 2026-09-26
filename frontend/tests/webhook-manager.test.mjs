import { test } from "node:test";
import assert from "node:assert/strict";
import { WebhookManager } from "../lib/webhook-manager.ts";

test("register stores the webhook and getAll returns it", () => {
  const r = WebhookManager.register("t1", "https://example.com/h", ["evt"]);
  assert.equal(r.success, true);
  const all = WebhookManager.getAll();
  assert.ok(all.find((w) => w.id === "t1"));
});

test("get returns the webhook and unregister removes it", () => {
  WebhookManager.register("t3", "https://example.com/h3", ["x"]);
  assert.ok(WebhookManager.get("t3"));
  const res = WebhookManager.unregister("t3");
  assert.equal(res.success, true);
  assert.equal(WebhookManager.get("t3"), null);
});

test("trigger posts to webhooks whose events match", async () => {
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    return {
      status: 200,
      url,
      ok: true,
      json: async () => opts && JSON.parse(opts.body),
    };
  };
  try {
    WebhookManager.register("t2", "https://example.com/h2", ["ping"]);
    const results = await WebhookManager.trigger("ping", { hello: 1 });
    assert.ok(Array.isArray(results));
    assert.ok(results.length >= 1);
    assert.equal(results[0].url, "https://example.com/h2");
    assert.equal(results[0].status, 200);
  } finally {
    globalThis.fetch = realFetch;
  }
});
