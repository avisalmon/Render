// SPR-I.11.2 improv: the left (soft) pedal is read, so the Play screen can pause on it.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const midi = require(path.join(__dirname, "..", "..", "static", "improv", "midi.js"));

test("the left pedal is controller 67: down at 64 and above, up below, on any channel", () => {
  assert.deepEqual(midi.parse([0xb0, 67, 127]), { type: "softpedal", down: true });
  assert.deepEqual(midi.parse([0xb0, 67, 64]), { type: "softpedal", down: true });
  assert.deepEqual(midi.parse([0xb0, 67, 63]), { type: "softpedal", down: false });
  assert.deepEqual(midi.parse([0xb3, 67, 0]), { type: "softpedal", down: false });
});

test("the sustain pedal is still the sustain pedal, and other controllers are still dropped", () => {
  assert.deepEqual(midi.parse([0xb0, 64, 127]), { type: "pedal", down: true });
  assert.equal(midi.parse([0xb0, 66, 127]), null);
  assert.equal(midi.parse([0xb0, 67]), null);
  assert.equal(midi.parse([0xb0, 67, 200]), null);
});
