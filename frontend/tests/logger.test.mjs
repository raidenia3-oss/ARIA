import { test } from "node:test";
import assert from "node:assert/strict";
import logger from "../lib/logger.js";

test("logger records integration events and retrieves them", () => {
  logger.clear();
  logger.event("test event", { a: 1 });
  const logs = logger.getLogs();
  assert.ok(Array.isArray(logs));
  assert.ok(logs.length >= 1);
  const last = logs[logs.length - 1];
  assert.equal(last.category, "integration");
  assert.equal(last.message, "test event");
  assert.deepEqual(last.meta, { a: 1 });
});

test("logger captures error message and stack", () => {
  logger.clear();
  const err = new Error("boom");
  logger.error("test", "failed op", err);
  const last = logger.getLogs().at(-1);
  assert.equal(last.level, "error");
  assert.equal(last.meta.message, "boom");
  assert.match(last.meta.stack, /boom/);
});

test("logger getLogs respects the limit argument", () => {
  logger.clear();
  for (let i = 0; i < 10; i++) logger.info("x", `m${i}`);
  assert.equal(logger.getLogs(3).length, 3);
  assert.equal(logger.getLogs().length, 10);
});

test("logger api helper stores timing + status", () => {
  logger.clear();
  logger.api("GET", "/api/x", 42, 200);
  const last = logger.getLogs().at(-1);
  assert.equal(last.category, "api");
  assert.deepEqual(last.meta, { ms: 42, status: 200 });
});
