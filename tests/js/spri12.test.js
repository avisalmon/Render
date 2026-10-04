// SPR-I.1.2 improv: the pure timing and MIDI maths behind the spike page.
// Run by tests/test_spri_1_2.py (node --test). No browser, no clock, no dependencies.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const timing = require(path.join("..", "..", "static", "improv", "timing.js"));
const midi = require(path.join("..", "..", "static", "improv", "midi.js"));

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} is not within ${eps} of ${b}`);

// ------------------------------------------------------------------ the anchor

test("a click scheduled at the anchor's own audio time is heard at the anchor's own performance time", () => {
  const anchor = timing.makeAnchor({ contextTime: 12.5, performanceTime: 40000 });
  close(timing.heardAt(anchor, 12.5), 40000);
});

test("a click scheduled later is heard later by exactly the gap, in milliseconds", () => {
  const anchor = timing.makeAnchor({ contextTime: 12.5, performanceTime: 40000 });
  close(timing.heardAt(anchor, 13.0), 40500);
  close(timing.heardAt(anchor, 12.0), 39500);
});

test("an anchor refuses nonsense instead of quietly producing numbers", () => {
  assert.throws(() => timing.makeAnchor({ contextTime: 0, performanceTime: 0 }), /output timestamp/i);
  assert.throws(() => timing.makeAnchor(undefined), /output timestamp/i);
  assert.throws(() => timing.makeAnchor({ contextTime: NaN, performanceTime: 5 }), /output timestamp/i);
});

// ---------------------------------------------------------------- click times

test("beat times are evenly spaced at the tempo", () => {
  const times = timing.beatTimes(10, 120, 4);
  assert.deepEqual(times.map((t) => +t.toFixed(6)), [10, 10.5, 11, 11.5]);
});

test("a tempo outside the sane range is refused", () => {
  assert.throws(() => timing.beatTimes(0, 5, 4), /tempo/i);
  assert.throws(() => timing.beatTimes(0, 400, 4), /tempo/i);
});

// -------------------------------------------------------------- nearest click

test("a note slightly after a click is positive, slightly before is negative", () => {
  const clicks = [1000, 1500, 2000];
  const late = timing.nearestClick(1530, clicks);
  assert.equal(late.index, 1);
  close(late.offsetMs, 30);
  const early = timing.nearestClick(1975, clicks);
  assert.equal(early.index, 2);
  close(early.offsetMs, -25);
});

test("a note exactly halfway belongs to the earlier click, deterministically", () => {
  assert.equal(timing.nearestClick(1250, [1000, 1500]).index, 0);
});

test("a note before the first click or after the last still finds its neighbour", () => {
  assert.equal(timing.nearestClick(900, [1000, 1500]).index, 0);
  assert.equal(timing.nearestClick(5000, [1000, 1500]).index, 1);
});

test("with no clicks there is nothing to compare against", () => {
  assert.equal(timing.nearestClick(1000, []), null);
});

// ---------------------------------------------------------------------- stats

test("the mean and the spread of a set of offsets", () => {
  const s = timing.stats([10, 20, 30]);
  assert.equal(s.n, 3);
  close(s.mean, 20);
  close(s.sd, 10); // sample standard deviation
  assert.equal(s.min, 10);
  assert.equal(s.max, 30);
});

test("one offset has a mean and no spread, and none has nothing at all", () => {
  const one = timing.stats([7]);
  assert.equal(one.mean, 7);
  assert.equal(one.sd, null);
  assert.equal(timing.stats([]).n, 0);
  assert.equal(timing.stats([]).mean, null);
});

test("a steady 40 ms late player and a scattered one are told apart by the spread", () => {
  const steady = timing.stats([38, 41, 40, 39, 42, 40]);
  const scattered = timing.stats([-60, 120, 10, 90, -30, 40]);
  assert.ok(Math.abs(steady.mean - 40) < 1);
  assert.ok(steady.sd < 5);
  assert.ok(scattered.sd > 50);
});

test("the verdict says when the numbers are too scattered to trust a single offset", () => {
  assert.equal(timing.verdict(timing.stats([38, 41, 40, 39, 42, 40])).usable, true);
  assert.equal(timing.verdict(timing.stats([-60, 120, 10, 90, -30, 40])).usable, false);
  assert.equal(timing.verdict(timing.stats([5, 6])).usable, false, "two taps prove nothing");
});

// ----------------------------------------------------------------- MIDI parse

test("note on carries the note and velocity, channel ignored", () => {
  assert.deepEqual(midi.parse([0x90, 60, 100]), { type: "on", note: 60, velocity: 100 });
  assert.deepEqual(midi.parse([0x95, 72, 1]), { type: "on", note: 72, velocity: 1 });
  assert.deepEqual(midi.parse([0x9f, 21, 127]), { type: "on", note: 21, velocity: 127 });
});

test("note on with velocity 0 is a note off", () => {
  assert.deepEqual(midi.parse([0x90, 60, 0]), { type: "off", note: 60 });
});

test("note off, on any channel", () => {
  assert.deepEqual(midi.parse([0x80, 60, 64]), { type: "off", note: 60 });
  assert.deepEqual(midi.parse([0x83, 61, 0]), { type: "off", note: 61 });
});

test("the sustain pedal is down at 64 and above, up below", () => {
  assert.deepEqual(midi.parse([0xb0, 64, 127]), { type: "pedal", down: true });
  assert.deepEqual(midi.parse([0xb0, 64, 64]), { type: "pedal", down: true });
  assert.deepEqual(midi.parse([0xb0, 64, 63]), { type: "pedal", down: false });
  assert.deepEqual(midi.parse([0xb2, 64, 0]), { type: "pedal", down: false });
});

test("everything else is dropped: other controllers, pitch bend, aftertouch, clock, sysex", () => {
  for (const msg of [[0xb0, 1, 50], [0xe0, 0, 64], [0xd0, 30], [0xa0, 60, 20], [0xf8], [0xfe], [0xf0, 1, 2, 0xf7], [0xc0, 5]]) {
    assert.equal(midi.parse(msg), null, JSON.stringify(msg));
  }
});

test("garbage is dropped, not thrown", () => {
  assert.equal(midi.parse([]), null);
  assert.equal(midi.parse(null), null);
  assert.equal(midi.parse([0x90]), null);
  assert.equal(midi.parse([0x90, 200, 100]), null, "a note number above 127 is not a note");
});

test("it accepts the Uint8Array that Web MIDI actually delivers", () => {
  assert.deepEqual(midi.parse(new Uint8Array([0x90, 64, 90])), { type: "on", note: 64, velocity: 90 });
});

test("note names", () => {
  assert.equal(midi.noteName(60), "C4");
  assert.equal(midi.noteName(61), "C#4");
  assert.equal(midi.noteName(21), "A0");
  assert.equal(midi.noteName(108), "C8");
});
