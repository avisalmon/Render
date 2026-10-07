// SPR-I.7.1 improv: the control keys at the top of the piano.
//
// The top key of an 88-key piano (MIDI 108) is the screen's primary button, the two below it the
// second and third. They act at note-on only, once per 400 ms, and are never played notes.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const C = require(path.join(__dirname, "..", "..", "static", "improv", "control.js"));

test("the top three keys of an 88-key piano are the three actions", () => {
  assert.equal(C.actionFor(108), "primary");
  assert.equal(C.actionFor(107), "secondary");
  assert.equal(C.actionFor(106), "tertiary");
});

test("every other key is not a control key", () => {
  for (const note of [0, 21, 60, 100, 105, 109, 127]) assert.equal(C.actionFor(note), null, String(note));
  assert.equal(C.actionFor(undefined), null);
});

test("the control zone is exactly the three keys", () => {
  assert.deepEqual([105, 106, 107, 108, 109].map(C.isControlNote), [false, true, true, true, false]);
});

test("each action has the name of its key to print on the button", () => {
  assert.equal(C.keyName("primary"), "C8");
  assert.equal(C.keyName("secondary"), "B7");
  assert.equal(C.keyName("tertiary"), "A#7");
  assert.equal(C.keyName("nothing"), "");
});

test("a note-on of a control key gives its action", () => {
  const c = C.createController();
  assert.equal(c.handle({ type: "on", note: 108, velocity: 80 }, 1000), "primary");
  assert.equal(c.handle({ type: "on", note: 107, velocity: 80 }, 1100), "secondary");
});

test("a note-off, the pedal and ordinary notes give nothing", () => {
  const c = C.createController();
  assert.equal(c.handle({ type: "off", note: 108 }, 0), null);
  assert.equal(c.handle({ type: "pedal", down: true }, 0), null);
  assert.equal(c.handle({ type: "on", note: 60, velocity: 90 }, 0), null);
  assert.equal(c.handle(null, 0), null);
});

test("the same key twice within 400 ms counts once, and again after", () => {
  const c = C.createController();
  assert.equal(c.handle({ type: "on", note: 108, velocity: 90 }, 1000), "primary");
  assert.equal(c.handle({ type: "on", note: 108, velocity: 90 }, 1399), null);
  assert.equal(c.handle({ type: "on", note: 108, velocity: 90 }, 1400), "primary");
});

test("a different key within 400 ms is not held back by the first", () => {
  const c = C.createController();
  assert.equal(c.handle({ type: "on", note: 108, velocity: 90 }, 1000), "primary");
  assert.equal(c.handle({ type: "on", note: 107, velocity: 90 }, 1100), "secondary");
});

test("choose picks the first button of the action that is shown and enabled", () => {
  const buttons = [
    { action: "primary", hidden: true, disabled: false },
    { action: "secondary", hidden: false, disabled: false },
    { action: "primary", hidden: false, disabled: true },
    { action: "primary", hidden: false, disabled: false },
    { action: "primary", hidden: false, disabled: false },
  ];
  assert.equal(C.choose(buttons, "primary"), 3);
  assert.equal(C.choose(buttons, "secondary"), 1);
});

test("choose finds nothing when no button of the action can be pressed", () => {
  assert.equal(C.choose([], "primary"), -1);
  assert.equal(C.choose([{ action: "primary", hidden: true, disabled: false }], "primary"), -1);
  assert.equal(C.choose([{ action: "primary", hidden: false, disabled: true }], "primary"), -1);
  assert.equal(C.choose([{ action: "secondary", hidden: false, disabled: false }], "tertiary"), -1);
});

test("the legend names the keys in order", () => {
  assert.equal(C.legend(), "C8 primary, B7 second, A#7 third");
});
