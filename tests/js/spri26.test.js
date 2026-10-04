// SPR-I.2.6 improv: changing tempo, key, swing and band while it plays, taking effect at the
// next bar line, and the audio output picker. The page is glue and is checked by the pytest
// wrapper and in a real browser; the rules are proved here.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const scheduler = require(path.join(root, "static", "improv", "scheduler.js"));
const play = require(path.join(root, "static", "improv", "play.js"));
const output = require(path.join(root, "static", "improv", "output.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));

const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases, intervals: q.intervals, roles: q.roles }));
const styles = library.styles.map((s, i) => ({ ...s, id: i + 1 }));
const progressions = library.progressions.map((p) => ({
  ...p,
  default_style: (styles.find((s) => s.slug === p.default_style) || {}).id || null,
}));

function build(slug, over = {}) {
  const p = progressions.find((x) => x.slug === slug);
  const style = over.style || play.pickStyle(p, styles);
  const settings = { ...play.defaultSettings(p, style), ...(over.settings || {}) };
  return play.buildPlan({ progression: p, style, qualities, settings });
}

// -------------------------------------------------------------------- scheduler

function fakeWorld() {
  const world = { t: 100, timers: [], seq: 0 };
  world.now = () => world.t;
  world.setTimer = (fn, ms) => {
    const handle = ++world.seq;
    world.timers.push({ handle, at: world.t + ms / 1000, fn });
    return handle;
  };
  world.clearTimer = (handle) => {
    world.timers = world.timers.filter((x) => x.handle !== handle);
  };
  world.run = (seconds) => {
    const until = world.t + seconds;
    for (;;) {
      world.timers.sort((a, b) => a.at - b.at);
      const next = world.timers[0];
      if (!next || next.at > until) break;
      world.timers.shift();
      world.t = next.at;
      next.fn();
    }
    world.t = until;
  };
  return world;
}

// A plan whose bass note says which plan a bar came from.
function markedPlan(mark, bars = 4, beats = 4) {
  return {
    ok: true,
    beatsPerBar: beats,
    bars: Array.from({ length: bars }, (_, index) => ({
      index,
      beats,
      events: [{ voice: "bass", beat: 0, beats: 1, midi: mark, velocity: 1 }],
    })),
  };
}

function harness() {
  const world = fakeWorld();
  const heard = [];
  const bars = [];
  const s = scheduler.createScheduler({
    now: world.now,
    setTimer: world.setTimer,
    clearTimer: world.clearTimer,
    onEvent: (event, when) => heard.push({ mark: event.midi, when }),
    onBar: (index, start, pass) => bars.push({ index, start, pass }),
  });
  return { world, s, heard, bars };
}

test("nextBarAt is when the first bar not yet queued starts, and nothing when it is not running", () => {
  const { world, s, bars } = harness();
  assert.equal(s.nextBarAt, null);
  s.start(markedPlan(1), { bpm: 120, at: 100.2 });
  assert.equal(s.nextBarAt, 100.2 + 2 * bars.length, "it is one bar after the last queued bar");
  world.run(0.5);
  assert.equal(s.nextBarAt, bars[bars.length - 1].start + 2);
  s.stop();
  assert.equal(s.nextBarAt, null);
});

test("a new plan takes over at the next bar line: bars already queued keep the old one", () => {
  const { world, s, heard, bars } = harness();
  s.start(markedPlan(40), { bpm: 120, at: 100.2 });
  world.run(1.0);
  const queuedBefore = bars.length;
  const at = s.setPlan(markedPlan(60));
  assert.equal(at, bars[queuedBefore - 1].start + 2, "it says when the change is heard");
  world.run(10);
  const old = heard.filter((h) => h.mark === 40);
  const fresh = heard.filter((h) => h.mark === 60);
  assert.equal(old.length, queuedBefore, "only the bars already queued stay old");
  assert.ok(fresh.length > 0);
  assert.ok(Math.min(...fresh.map((h) => h.when)) >= at - 1e-9, "nothing new sounds before the change time");
  assert.ok(Math.max(...old.map((h) => h.when)) < at, "nothing old sounds after it");
});

test("a plan swap leaves no gap or overlap in the bars", () => {
  const { world, s, bars } = harness();
  s.start(markedPlan(40), { bpm: 120, at: 100.2 });
  world.run(1.0);
  s.setPlan(markedPlan(60));
  world.run(12);
  for (let k = 1; k < bars.length; k++) assert.ok(Math.abs(bars[k].start - bars[k - 1].start - 2) < 1e-9, `bar ${k}`);
});

test("the loop keeps going on the new plan, pass after pass, from the same place", () => {
  const { world, s, heard, bars } = harness();
  s.start(markedPlan(40, 2), { bpm: 240, at: 100.2 });
  world.run(0.3);
  s.setPlan(markedPlan(60, 2));
  world.run(6);
  const last = heard.slice(-6).map((h) => h.mark);
  assert.deepEqual([...new Set(last)], [60]);
  const indexes = bars.map((b) => b.index);
  for (let k = 1; k < indexes.length; k++) assert.equal(indexes[k], (indexes[k - 1] + 1) % 2);
});

test("a plan of a different shape is refused and the band plays on as before", () => {
  const { world, s, heard } = harness();
  s.start(markedPlan(40, 4), { bpm: 120, at: 100.2 });
  world.run(0.5);
  assert.equal(s.setPlan(markedPlan(60, 5)), null, "a different number of bars");
  assert.equal(s.setPlan(markedPlan(60, 4, 3)), null, "a different bar length");
  world.run(12);
  assert.ok(heard.every((h) => h.mark === 40));
});

test("a plan cannot be swapped into a band that is not running", () => {
  const { s } = harness();
  assert.equal(s.setPlan(markedPlan(60)), null);
  const { world, s: stopped } = harness();
  stopped.start(markedPlan(40), { bpm: 120, at: 100.2 });
  stopped.stop();
  assert.equal(stopped.setPlan(markedPlan(60)), null);
  world.run(1);
});

test("a swap and a tempo change together both start on the same bar line", () => {
  const { world, s, heard, bars } = harness();
  s.start(markedPlan(40), { bpm: 120, at: 100.2 });
  world.run(1.0);
  s.setBpm(60);
  const at = s.setPlan(markedPlan(60));
  world.run(20);
  const first = bars.find((b) => b.start >= at - 1e-9);
  const lengths = [];
  for (let k = 1; k < bars.length; k++) lengths.push(Number((bars[k].start - bars[k - 1].start).toFixed(6)));
  const turn = bars.indexOf(first);
  assert.equal(lengths[turn - 1], 2, "the bar before the change keeps its length");
  assert.equal(lengths[turn], 4, "the first new bar is at the new tempo");
  assert.equal(heard.find((h) => h.mark === 60).when, first.start);
});

// ------------------------------------------------------------------------ play.js

test("changing the key, the swing or the band at the same bar length can go live", () => {
  const now = build("ii-v-i-major");
  assert.equal(now.ok, true);
  assert.equal(play.canGoLive(now, build("ii-v-i-major", { settings: { key: "Eb" } })), true);
  assert.equal(play.canGoLive(now, build("ii-v-i-major", { settings: { swing: "straight" } })), true);
  const other = styles.find((s) => s.time_signature === "4/4" && s.genre === "latin");
  assert.equal(play.canGoLive(now, build("ii-v-i-major", { style: other })), true);
});

test("a change that alters the shape of the take cannot go live", () => {
  const now = build("twelve-bar-blues");
  assert.equal(play.canGoLive(now, build("twelve-bar-blues", { settings: { countIn: 2 } })), false);
  assert.equal(play.canGoLive(now, build("twelve-bar-blues", { settings: { first: "1", last: "4" } })), false);
  assert.equal(play.canGoLive(now, build("twelve-bar-blues", { settings: { metronome: true } })), false);
  assert.equal(play.canGoLive(now, build("ii-v-i-major")), false, "a different progression");
});

test("a build that failed, or no build, never goes live", () => {
  const now = build("ii-v-i-major");
  assert.equal(play.canGoLive(now, { ok: false, error: "no" }), false);
  assert.equal(play.canGoLive(null, now), false);
  assert.equal(play.canGoLive(now, null), false);
});

test("what stays locked while it plays, and what moves, do not overlap and cover every setting", () => {
  assert.deepEqual([...play.LIVE_CONTROLS].sort(), ["bpm", "key", "style", "swing"]);
  assert.deepEqual([...play.LOCKED_CONTROLS].sort(), ["countin", "first", "last", "metronome", "progression"]);
  for (const id of play.LIVE_CONTROLS) assert.ok(!play.LOCKED_CONTROLS.includes(id));
});

// ------------------------------------------------------------------------ output

const device = (kind, deviceId, label = "") => ({ kind, deviceId, label });

test("the output picker lists outputs only, with the system default first", () => {
  const list = output.choices([
    device("audioinput", "mic", "Microphone"),
    device("audiooutput", "a1", "Speakers"),
    device("audiooutput", "a2", "USB Audio"),
    device("videoinput", "cam", "Camera"),
  ]);
  assert.deepEqual(list.map((c) => c.id), ["", "a1", "a2"]);
  assert.equal(list[0].label, "System default");
  assert.equal(list[2].label, "USB Audio");
});

test("the browser's own default and communications entries are not listed twice", () => {
  const list = output.choices([
    device("audiooutput", "default", "Default - Speakers (Realtek)"),
    device("audiooutput", "communications", "Communications - Headset"),
    device("audiooutput", "a1", "Speakers (Realtek)"),
  ]);
  assert.deepEqual(list.map((c) => c.id), ["", "a1"]);
  assert.equal(list[0].label, "System default: Speakers (Realtek)");
});

test("an output the browser will not name is numbered, so two can be told apart", () => {
  const list = output.choices([device("audiooutput", "a1"), device("audiooutput", "a2", "   ")]);
  assert.deepEqual(list.map((c) => c.label), ["System default", "Output 1", "Output 2"]);
  assert.equal(output.hasNames([device("audiooutput", "a1")]), false);
  assert.equal(output.hasNames([device("audiooutput", "a1", "Speakers")]), true);
});

test("no devices at all still gives the default, and junk in the list is ignored", () => {
  assert.deepEqual(output.choices([]).map((c) => c.id), [""]);
  assert.deepEqual(output.choices(null).map((c) => c.id), [""]);
  assert.deepEqual(output.choices([null, undefined, {}]).map((c) => c.id), [""]);
});

test("a chosen output that was unplugged falls back to the default", () => {
  const list = output.choices([device("audiooutput", "a1", "USB Audio")]);
  assert.equal(output.stillThere(list, "a1"), true);
  assert.equal(output.stillThere(list, "gone"), false);
  assert.equal(output.stillThere(list, ""), true);
});

test("the picker is offered only where the browser can send sound to a chosen output", () => {
  assert.equal(output.supported({ setSinkId() {} }, { enumerateDevices() {} }), true);
  assert.equal(output.supported({}, { enumerateDevices() {} }), false, "Safari has no setSinkId");
  assert.equal(output.supported({ setSinkId() {} }, {}), false);
  assert.equal(output.supported(null, null), false);
});
