import { test } from "node:test";
import assert from "node:assert/strict";
import {
  sortEventsByTimestamp,
  formatEventTime,
  chapterStatusLabel,
  parseListInput,
  slugify,
} from "../lib/story-format.js";

test("sortEventsByTimestamp orders events ascending without mutating input", () => {
  const input = [{ timestamp: 30 }, { timestamp: 10 }, {}];
  const sorted = sortEventsByTimestamp(input);
  assert.deepEqual(
    sorted.map((e) => e.timestamp || 0),
    [0, 10, 30]
  );
  assert.equal(input[0].timestamp, 30, "input must not be mutated");
});

test("formatEventTime returns dash for empty values", () => {
  assert.equal(formatEventTime(0), "—");
  assert.equal(formatEventTime(undefined), "—");
  assert.ok(typeof formatEventTime(1000) === "string");
});

test("chapterStatusLabel maps known statuses and passes through unknown", () => {
  assert.equal(chapterStatusLabel("planned"), "Planificado");
  assert.equal(chapterStatusLabel("completed"), "Completado");
  assert.equal(chapterStatusLabel("custom_state"), "custom_state");
  assert.equal(chapterStatusLabel(""), "—");
});

test("parseListInput splits by comma and newline and trims", () => {
  assert.deepEqual(parseListInput("a, b\nc ,, d"), ["a", "b", "c", "d"]);
  assert.deepEqual(parseListInput(""), []);
  assert.deepEqual(parseListInput(null), []);
});

test("slugify normalizes accents and spaces", () => {
  assert.equal(slugify("La Odisea de Ámbar"), "la_odisea_de_ambar");
  assert.equal(slugify("  --Hola Mundo--  "), "hola_mundo");
});
