// SPR-I.2.4 improv: the Play screen's logic (play.js), the count-in loop in the scheduler
// and the click voice. The page itself is glue and is checked by the pytest wrapper
// (every control the script reads exists in the template).

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const chart = require(path.join(root, "static", "improv", "chart.js"));
const scheduler = require(path.join(root, "static", "improv", "scheduler.js"));
const synthLib = require(path.join(root, "static", "improv", "synth.js"));
const play = require(path.join(root, "static", "improv", "play.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));

const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases, intervals: q.intervals, roles: q.roles }));
// The API gives styles an id and a progression the id of its default style.
const styles = library.styles.map((s, i) => ({ ...s, id: i + 1 }));
const progressions = library.progressions.map((p) => ({
  ...p,
  default_style: (styles.find((s) => s.slug === p.default_style) || {}).id || null,
}));
const progression = (slug) => progressions.find((p) => p.slug === slug);
const styleOf = (p) => play.pickStyle(p, styles);
const pc = (m) => m % 12;

function build(slug, over = {}) {
  const p = progression(slug);
  const style = over.style || styleOf(p);
  const settings = { ...play.defaultSettings(p, style), ...(over.settings || {}) };
  return { p, style, settings, built: play.buildPlan({ progression: p, style, qualities, settings }) };
}

// ---------------------------------------------------------------- small rules

test("swing: a swung groove keeps its ratio, a straight one swings medium when asked, straight is always 0.5", () => {
  const swung = styles.find((s) => s.slug === "medium-swing");
  const straight = styles.find((s) => s.slug === "rock-straight");
  assert.equal(play.swingRatioFor(swung, "swing"), 0.62);
  assert.equal(play.swingRatioFor(swung, "straight"), 0.5);
  assert.equal(play.swingRatioFor(straight, "swing"), 0.62);
  assert.equal(play.swingRatioFor(straight, "straight"), 0.5);
  assert.equal(play.defaultSwingMode(swung), "swing");
  assert.equal(play.defaultSwingMode(straight), "straight");
});

test("tempo is held inside what the band's style allows, and a blank or junk value gets the default", () => {
  const style = styles.find((s) => s.slug === "medium-swing");
  assert.equal(play.clampTempo(style, 1000), style.max_tempo);
  assert.equal(play.clampTempo(style, 5), style.min_tempo);
  assert.equal(play.clampTempo(style, "132"), 132);
  assert.equal(play.clampTempo(style, 99.6), 100);
  assert.equal(play.clampTempo(style, ""), Math.min(style.max_tempo, Math.max(style.min_tempo, style.default_tempo)));
  assert.equal(play.clampTempo(style, "abc") >= style.min_tempo, true);
});

test("a progression uses the band it asks for, or the first that fits its bar length", () => {
  const p = progression("twelve-bar-blues");
  assert.equal(play.pickStyle(p, styles).slug, "blues-shuffle");
  assert.equal(play.pickStyle({ ...p, default_style: null }, styles).time_signature, "4/4");
  assert.equal(play.pickStyle({ ...p, default_style: null, time_signature: "3/4" }, styles), null);
});

test("the key list is twelve keys, in the progression's major or minor, home key spelled as written", () => {
  const major = play.keyOptions("Eb");
  assert.equal(major.length, 12);
  assert.ok(major.includes("Eb") && major.includes("C") && major.includes("F#"));
  const minor = play.keyOptions("Am");
  assert.equal(minor.length, 12);
  assert.ok(minor.every((k) => k.endsWith("m")));
  assert.ok(minor.includes("Am"));
  const sharp = play.keyOptions("C#");
  assert.ok(sharp.includes("C#") && !sharp.includes("Db"), "the home key keeps its own spelling");
  assert.equal(sharp.length, 12);
});

test("the loop range is typed 1-based and inclusive, and refused when it makes no sense", () => {
  assert.deepEqual(play.rangeOf("", "", 8), { ok: true, from: 0, to: 8, whole: true });
  assert.deepEqual(play.rangeOf(3, 5, 8), { ok: true, from: 2, to: 5, whole: false });
  assert.deepEqual(play.rangeOf("", 4, 8), { ok: true, from: 0, to: 4, whole: false });
  assert.deepEqual(play.rangeOf(5, "", 8), { ok: true, from: 4, to: 8, whole: false });
  assert.deepEqual(play.rangeOf(1, 8, 8), { ok: true, from: 0, to: 8, whole: true });
  assert.equal(play.rangeOf(5, 3, 8).ok, false);
  assert.equal(play.rangeOf(0, 3, 8).ok, false);
  assert.equal(play.rangeOf(1, 9, 8).ok, false);
  assert.equal(play.rangeOf(1.5, 3, 8).ok, false);
  assert.match(play.rangeOf(1, 9, 8).error, /bars 1 to 8/);
});

// ----------------------------------------------------------------- the plan

test("every progression plays with the band it asks for, at its own settings", () => {
  for (const p of progressions) {
    const { built } = build(p.slug);
    assert.equal(built.ok, true, `${p.slug}: ${built.error}`);
    assert.equal(built.countInBars, 1);
    assert.equal(built.plan.bars.length, built.chart.bars.length + 1);
    assert.equal(built.loopFrom, 1);
  }
});

test("the plan opens with the count-in clicks, then the chosen bars, in one numbering", () => {
  const { built } = build("ii-v-i-major", { settings: { countIn: 2 } });
  const bars = built.plan.bars;
  assert.deepEqual(bars.map((b) => b.index), bars.map((_, i) => i));
  assert.deepEqual(bars.map((b) => b.countIn), [true, true, false, false, false, false].slice(0, bars.length));
  for (const b of bars.slice(0, 2)) {
    assert.deepEqual(b.events.map((e) => [e.voice, e.beat]), [["click", 0], ["click", 1], ["click", 2], ["click", 3]]);
    assert.equal(b.events[0].accent, true);
    assert.ok(b.events[0].velocity > b.events[1].velocity, "the first click is the loudest");
  }
  assert.ok(bars[2].events.some((e) => e.voice === "bass"));
  assert.equal(built.loopFrom, 2);
});

test("no count-in means the first bar is the chart's first bar", () => {
  const { built } = build("ii-v-i-major", { settings: { countIn: 0 } });
  assert.equal(built.countInBars, 0);
  assert.equal(built.loopFrom, 0);
  assert.equal(built.plan.bars[0].countIn, false);
  assert.equal(built.plan.bars.length, built.chart.bars.length);
});

test("the count-in is capped at two bars and never negative", () => {
  assert.equal(build("ii-v-i-major", { settings: { countIn: 9 } }).built.countInBars, 2);
  assert.equal(build("ii-v-i-major", { settings: { countIn: -3 } }).built.countInBars, 0);
});

test("a key change shows in the chart and moves what the band plays", () => {
  const home = build("ii-v-i-major").built;
  const moved = build("ii-v-i-major", { settings: { key: "Eb" } }).built;
  assert.equal(home.chart.bars[0].chords[0].name, "Dm7");
  assert.equal(moved.chart.bars[0].chords[0].name, "Fm7");
  const rootOf = (b) => b.plan.bars.find((x) => !x.countIn).events.find((e) => e.voice === "bass");
  assert.equal(pc(rootOf(moved).midi), 5);
  assert.equal(pc(rootOf(home).midi), 2);
});

test("the original chart is not changed by playing it in another key", () => {
  const p = progression("ii-v-i-major");
  const before = JSON.stringify(p);
  build("ii-v-i-major", { settings: { key: "F#" } });
  assert.equal(JSON.stringify(p), before);
});

test("a loop range plays just those bars, and the chart knows which are inside", () => {
  const { built } = build("twelve-bar-blues", { settings: { first: 5, last: 8, countIn: 1 } });
  assert.equal(built.plan.bars.length, 1 + 4);
  assert.equal(built.from, 4);
  assert.equal(built.to, 8);
  const rows = play.layoutBars(built.chart, built.from, built.to);
  const cells = rows.flat();
  assert.equal(cells.length, 12);
  assert.deepEqual(cells.filter((c) => c.inLoop).map((c) => c.number), [5, 6, 7, 8]);
});

test("metronome only: a click on every beat of the chosen bars, nothing else", () => {
  const { built } = build("ii-v-i-major", { settings: { metronome: true, countIn: 0 } });
  assert.equal(built.metronome, true);
  for (const b of built.plan.bars) {
    assert.ok(b.events.every((e) => e.voice === "click"));
    assert.equal(b.events.length, 4);
  }
  assert.equal(built.plan.bars.length, built.chart.bars.length);
});

test("metronome only respects the loop range", () => {
  const { built } = build("twelve-bar-blues", { settings: { metronome: true, countIn: 0, first: 2, last: 3 } });
  assert.equal(built.plan.bars.length, 2);
});

test("straight takes the swing out of the same band", () => {
  const swung = build("ii-v-i-major", { settings: { swing: "swing", countIn: 0 } }).built;
  const straight = build("ii-v-i-major", { settings: { swing: "straight", countIn: 0 } }).built;
  const offbeat = (b) => b.plan.bars[0].events.filter((e) => e.voice === "drums" && e.inst === "ride").map((e) => e.beat);
  assert.ok(offbeat(swung).includes(1.62));
  assert.ok(offbeat(straight).includes(1.5));
});

test("a progression a style cannot play is refused with the reason, not played badly", () => {
  const waltz = { ...progression("ii-v-i-major"), time_signature: "3/4", chart: "| C | F | G |" };
  const out = play.buildPlan({ progression: waltz, style: styles[0], qualities, settings: play.defaultSettings(waltz, styles[0]) });
  assert.equal(out.ok, false);
  assert.match(out.error, /3 beats/);
});

test("bad input says what is wrong", () => {
  const p = progression("ii-v-i-major");
  const style = styleOf(p);
  const run = (settings, prog = p) => play.buildPlan({ progression: prog, style, qualities, settings: { ...play.defaultSettings(prog, style), ...settings } });
  assert.match(run({ key: "H" }).error, /not a key/);
  assert.match(run({ first: 9, last: 2 }).error, /bars 1 to|comes before/);
  const broken = run({}, { ...p, chart: "| Dm7 | Zzz9 |" });
  assert.equal(broken.ok, false);
  assert.match(broken.error, /line \d+, column \d+/);
  assert.equal(play.buildPlan({ progression: { ...p, time_signature: "7/8" }, style, qualities, settings: {} }).ok, false);
});

// ------------------------------------------------------- what the screen lights

test("the screen lights the right bar in the right pass, and the count-in separately", () => {
  const { built } = build("twelve-bar-blues", { settings: { first: 5, last: 8, countIn: 1 } });
  assert.deepEqual(play.litFor(built, { index: 0, pass: 0, beat: 2.5 }), { countIn: true, number: 1, of: 1, beat: 2.5, bar: null, pass: 0 });
  assert.deepEqual(play.litFor(built, { index: 1, pass: 0, beat: 0.5 }), { countIn: false, bar: 4, beat: 0.5, pass: 0 });
  assert.equal(play.litFor(built, { index: 4, pass: 2, beat: 1 }).bar, 7);
  assert.equal(play.litFor(built, { index: 4, pass: 2, beat: 1 }).pass, 2);
  assert.equal(play.litFor(built, null), null);
  assert.equal(play.litFor(built, { index: 99, pass: 0, beat: 0 }), null);
});

test("the chart is laid out four bars to a row with chord names and key changes marked", () => {
  const { built } = build("key-change-up-a-tone");
  const rows = play.layoutBars(built.chart, 0, built.chart.bars.length);
  assert.ok(rows.every((r) => r.length <= 4));
  assert.equal(rows[0][0].number, 1);
  const changes = rows.flat().filter((c) => c.keyChange);
  assert.equal(changes.length, 1, "the key change is marked once, where it happens");
  assert.ok(rows.flat().every((c) => c.chords.length >= 1 && c.chords.every((n) => typeof n === "string")));
});

// ------------------------------------------------- the scheduler with a count-in

function fakeWorld() {
  const world = { t: 100, timers: [], seq: 0 };
  world.now = () => world.t;
  world.setTimer = (fn, ms) => {
    const handle = ++world.seq;
    world.timers.push({ handle, at: world.t + ms / 1000, fn });
    return handle;
  };
  world.clearTimer = (h) => {
    world.timers = world.timers.filter((x) => x.handle !== h);
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

test("the count-in plays once and the loop comes back to the first chart bar", () => {
  const { built } = build("ii-v-i-major", { settings: { countIn: 1 } });
  const world = fakeWorld();
  const bars = [];
  const s = scheduler.createScheduler({
    now: world.now,
    setTimer: world.setTimer,
    clearTimer: world.clearTimer,
    onEvent: () => {},
    onBar: (index, start, pass) => bars.push([index, pass]),
  });
  s.start(built.plan, { bpm: 300, at: 100.1, loopFrom: built.loopFrom });
  world.run(8);
  const n = built.plan.bars.length;
  assert.deepEqual(bars.slice(0, n + 2), [...Array(n).keys()].map((i) => [i, 0]).concat([[1, 1], [2, 1]]));
  assert.equal(bars.filter(([i]) => i === 0).length, 1, "the count-in bar is never played again");
});

test("the first click lands exactly on the scheduled start", () => {
  const { built } = build("ii-v-i-major", { settings: { countIn: 1 } });
  const world = fakeWorld();
  const heard = [];
  const s = scheduler.createScheduler({
    now: world.now,
    setTimer: world.setTimer,
    clearTimer: world.clearTimer,
    onEvent: (e, when) => heard.push({ e, when }),
  });
  s.start(built.plan, { bpm: 120, at: 100.5, loopFrom: built.loopFrom });
  world.run(3);
  const clicks = heard.filter((h) => h.e.voice === "click");
  assert.deepEqual(clicks.map((c) => Number(c.when.toFixed(6))), [100.5, 101, 101.5, 102]);
  const firstBass = heard.find((h) => h.e.voice === "bass");
  assert.ok(Math.abs(firstBass.when - 102.5) < 1e-9, "the band comes in right after the count-in");
});

test("a loopFrom outside the plan is held inside it", () => {
  const world = fakeWorld();
  const bars = [];
  const s = scheduler.createScheduler({ now: world.now, setTimer: world.setTimer, clearTimer: world.clearTimer, onEvent: () => {}, onBar: (i) => bars.push(i) });
  const plan = { ok: true, beatsPerBar: 4, bars: [0, 1].map((index) => ({ index, beats: 4, events: [] })) };
  s.start(plan, { bpm: 300, at: 100.1, loopFrom: 40 });
  world.run(3);
  assert.deepEqual(bars.slice(0, 4), [0, 1, 1, 1]);
});

// -------------------------------------------------------------------- the click

function recordingContext() {
  const made = [];
  const param = () => {
    const p = { value: 0, calls: [] };
    p.setValueAtTime = (v, t) => (p.calls.push(["set", v, t]), p);
    p.linearRampToValueAtTime = (v, t) => (p.calls.push(["lin", v, t]), p);
    p.exponentialRampToValueAtTime = (v, t) => (p.calls.push(["exp", v, t]), p);
    return p;
  };
  const node = (kind, extra) => {
    const n = { kind, connect: (x) => x, start(t) { n.started = t; }, stop(t) { n.stopped = t; }, ...extra };
    made.push(n);
    return n;
  };
  return {
    made,
    ctx: {
      currentTime: 5,
      sampleRate: 8000,
      destination: node("destination"),
      createGain: () => node("gain", { gain: param() }),
      createOscillator: () => node("osc", { frequency: param() }),
      createBiquadFilter: () => node("filter", { frequency: param(), Q: param() }),
      createBufferSource: () => node("source"),
      createBuffer: (c, length) => ({ getChannelData: () => new Float32Array(length) }),
      createDynamicsCompressor: () => node("limiter", { threshold: param(), knee: param(), ratio: param(), attack: param(), release: param() }),
    },
  };
}

test("the click ticks on time, higher on the beat than off it", () => {
  const hz = (accent) => {
    const { ctx, made } = recordingContext();
    const synth = synthLib.createSynth(ctx);
    const before = made.filter((n) => n.kind === "osc").length;
    synth.play({ voice: "click", velocity: 1, accent }, 6, 0.1);
    const osc = made.filter((n) => n.kind === "osc").slice(before);
    assert.equal(osc.length, 1);
    assert.equal(osc[0].started, 6);
    assert.ok(osc[0].stopped > 6);
    return osc[0].frequency.calls[0][1];
  };
  assert.ok(hz(true) > hz(false));
});

test("the click has its own level and mute, so it can be the only thing you hear", () => {
  const { ctx } = recordingContext();
  const synth = synthLib.createSynth(ctx);
  assert.ok(synth.groups.includes("click"));
  assert.doesNotThrow(() => {
    synth.setLevel("click", 0.5);
    synth.setMuted("click", true);
    synth.setMuted("click", false);
  });
});
