// SPR-I.14.2 improv: hearing the piano through a microphone. Run with: node --test tests/js/spri141.test.js
// The signals are made here: piano-like notes (overtones falling away, a slight stretch, a decay) plus noise.
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../../static/improv/pitch.js");

const SR = 44100;
const HOP = 1024;
const FRAME = 4096;

let seed = 7;
const random = () => {
  seed = (seed * 1664525 + 1013904223) % 4294967296;
  return seed / 4294967296;
};

function tone(midi, seconds, amp = 0.2, decay = 2.5) {
  const n = Math.floor(seconds * SR);
  const out = new Float32Array(n);
  const f0 = P.hz(midi);
  for (let h = 1; h <= 10; h++) {
    const f = f0 * h * Math.sqrt(1 + 0.0001 * h * h);
    if (f > SR / 2) break;
    const a = amp / Math.pow(h, 1.1);
    const life = decay / (1 + 0.5 * h);
    const phase = random() * 2 * Math.PI;
    for (let i = 0; i < n; i++) {
      const t = i / SR;
      out[i] += a * Math.exp(-t / life) * Math.sin(2 * Math.PI * f * t + phase) * Math.min(1, t / 0.004);
    }
  }
  return out;
}

function place(total, parts) {
  const out = new Float32Array(Math.floor(total * SR));
  for (const [at, signal] of parts) {
    const start = Math.floor(at * SR);
    for (let i = 0; i < signal.length && start + i < out.length; i++) out[start + i] += signal[i];
  }
  return out;
}

function noise(seconds, amp) {
  const out = new Float32Array(Math.floor(seconds * SR));
  for (let i = 0; i < out.length; i++) out[i] = (random() * 2 - 1) * amp;
  return out;
}

const an = P.makeAnalyser(SR, FRAME);
const heardAt = (signal, at) => {
  const start = Math.floor(at * SR);
  return P.analyse(an, signal.subarray(start, start + FRAME)).notes.map((n) => n.midi).sort((a, b) => a - b);
};

// Feeds a signal to a tracker frame by frame and gathers the events.
function track(signal, options) {
  const tracker = P.createTracker(SR, options);
  const events = [];
  for (let end = FRAME; end <= signal.length; end += HOP) {
    const frame = signal.subarray(end - FRAME, end);
    events.push(...tracker.push(frame, (end / SR) * 1000));
  }
  return events;
}

test("every single note from C2 to C7 is heard as itself and nothing else", () => {
  for (let midi = P.LOW; midi <= P.HIGH; midi++) {
    assert.deepEqual(heardAt(tone(midi, 1), 0.4), [midi], `note ${midi}`);
  }
});

test("a sine wave of the pitch alone is not enough; overtones make a note", () => {
  const n = SR;
  const sine = new Float32Array(n);
  for (let i = 0; i < n; i++) sine[i] = 0.2 * Math.sin((2 * Math.PI * 440 * i) / SR);
  assert.deepEqual(heardAt(sine, 0.4), []);
});

test("chords of three and four notes are read from C3 up", () => {
  const chords = [
    [60, 64, 67],
    [48, 55, 64],
    [50, 57, 60, 65],
    [53, 57, 60],
    [55, 62],
    [64, 72],
    [72, 76, 79],
    [57, 60, 64],
    [59, 62, 67],
  ];
  for (const notes of chords) {
    const signal = place(1, notes.map((m) => [0, tone(m, 1)]));
    assert.deepEqual(heardAt(signal, 0.4), [...notes].sort((a, b) => a - b), `chord ${notes}`);
  }
});

test("silence, a quiet room and loud hiss are not notes", () => {
  assert.deepEqual(heardAt(new Float32Array(SR), 0.4), []);
  assert.deepEqual(heardAt(noise(1, 0.002), 0.4), []);
  assert.deepEqual(heardAt(noise(1, 0.05), 0.4), []);
});

test("a note over a quiet room is still the note", () => {
  const signal = place(1, [[0, tone(67, 1)], [0, noise(1, 0.004)]]);
  assert.deepEqual(heardAt(signal, 0.4), [67]);
});

test("a tracker gives the same note on and note off as a keyboard, close to the true times", () => {
  const signal = place(2.2, [[0.3, tone(69, 0.6)], [1.3, tone(72, 0.6)]]);
  const events = track(signal);
  const kinds = events.map((e) => `${e.type}${e.note}`);
  assert.deepEqual(kinds, ["on69", "off69", "on72", "off72"]);
  const on69 = events[0];
  const on72 = events[2];
  assert.ok(Math.abs(on69.t - 300) <= 50, `A4 on at ${on69.t}`);
  assert.ok(Math.abs(on72.t - 1300) <= 50, `C5 on at ${on72.t}`);
  assert.ok(events[1].t > on69.t && events[1].t < on72.t);
  assert.ok(events.every((e) => e.type === "off" || (e.velocity >= 20 && e.velocity <= 120)));
});

test("a chord struck together arrives as three note ons at about the same time", () => {
  const signal = place(1.6, [[0.4, tone(60, 0.8)], [0.4, tone(64, 0.8)], [0.4, tone(67, 0.8)]]);
  const ons = track(signal).filter((e) => e.type === "on");
  assert.deepEqual(ons.map((e) => e.note).sort((a, b) => a - b), [60, 64, 67]);
  const times = ons.map((e) => e.t);
  assert.ok(Math.max(...times) - Math.min(...times) <= 25, `spread ${times}`);
  assert.ok(ons.every((e) => Math.abs(e.t - 400) <= 50), `times ${times}`);
});

test("the same note struck again while it still rings is two notes", () => {
  const signal = place(2, [[0.3, tone(65, 0.5, 0.2, 0.6)], [0.8, tone(65, 0.6)]]);
  const events = track(signal);
  const ons = events.filter((e) => e.type === "on" && e.note === 65);
  assert.equal(ons.length, 2, events.map((e) => `${e.type}${e.note}@${Math.round(e.t)}`).join(","));
  assert.ok(Math.abs(ons[1].t - 800) <= 70, `second strike at ${ons[1].t}`);
});

test("a note joining a held one does not strike the held one again", () => {
  const signal = place(2.5, [[0.3, tone(48, 2)], [0.9, tone(55, 1.2)], [1.4, tone(64, 0.9)]]);
  const kinds = track(signal).filter((e) => e.type === "on").map((e) => e.note);
  assert.deepEqual(kinds, [48, 55, 64]);
});

test("the same note struck again after a lift is two notes", () => {
  const signal = place(2.4, [[0.3, tone(65, 0.5)], [1.2, tone(65, 0.6)]]);
  const kinds = track(signal).map((e) => `${e.type}${e.note}`);
  assert.deepEqual(kinds, ["on65", "off65", "on65", "off65"]);
});

test("a run of notes comes out in order with none doubled", () => {
  const notes = [60, 62, 64, 65, 67, 69, 71, 72];
  const parts = notes.map((m, i) => [0.3 + i * 0.32, tone(m, 0.3)]);
  const signal = place(3.4, parts);
  const ons = track(signal).filter((e) => e.type === "on");
  assert.deepEqual(ons.map((e) => e.note), notes);
  ons.forEach((e, i) => assert.ok(Math.abs(e.t - (300 + i * 320)) <= 60, `note ${i} at ${e.t}`));
});

test("a sound that was never a note makes no events, and a held note makes one pair", () => {
  assert.deepEqual(track(noise(1.5, 0.05)), []);
  const held = track(place(3, [[0.2, tone(48, 2.2)]]));
  assert.deepEqual(held.map((e) => `${e.type}${e.note}`), ["on48", "off48"]);
});

test("velocity follows loudness", () => {
  assert.ok(P.velocityOf(0.2) > P.velocityOf(0.02));
  assert.ok(P.velocityOf(10) <= 120 && P.velocityOf(0.00001) >= 20);
});
