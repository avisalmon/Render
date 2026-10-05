// SPR-I.6.2 improv: how the Takes screen speaks of a take whose notes were cleared.
//
// An unkept take loses its events after thirty days and keeps its score. Replay and Keep need the
// notes, so the screen says why they are off instead of leaving a dead button.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const T = require(path.join(__dirname, "..", "..", "static", "improv", "takes.js"));

const take = (over) => ({
  id: 1, tempo: 90, key: "C", bars: 4, score: 80, is_kept: false, started_at: "2026-09-01T10:00:00Z",
  events: [{ t_ms: 0, type: "on", note: 60, velocity: 90 }], metrics: { notes: 25 }, ...over,
});

test("a take with notes is not cleared and says nothing", () => {
  assert.equal(T.cleared(take()), false);
  assert.equal(T.clearedNote(take()), "");
});

test("a take with no events is cleared and says why", () => {
  assert.equal(T.cleared(take({ events: [] })), true);
  assert.equal(T.clearedNote(take({ events: [] })), "The notes were cleared after 30 days. The score stays.");
});

test("a missing events field counts as cleared, and nothing is not a take", () => {
  assert.equal(T.cleared(take({ events: undefined })), true);
  assert.equal(T.cleared(null), true);
});

test("a kept take is never described as cleared", () => {
  assert.equal(T.clearedNote(take({ events: [], is_kept: true })), "");
});

test("a cleared take still reads its note count and score from what stayed", () => {
  const d = T.describe(take({ events: [], score: 77 }), { titles: {} });
  assert.equal(d.notes, 25);
  assert.equal(d.score, 77);
});
