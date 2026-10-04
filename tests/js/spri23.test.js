// SPR-I.2.3 improv: the band engine. The planner (band.js), the look-ahead scheduler
// (scheduler.js) and the synth voices (synth.js) with a recording stand-in for the
// AudioContext. What cannot be proved here is how it sounds; Avi's ears do that at the
// end of the epic. What is proved here is what the band plays, and when.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const chart = require(path.join(root, "static", "improv", "chart.js"));
const band = require(path.join(root, "static", "improv", "band.js"));
const scheduler = require(path.join(root, "static", "improv", "scheduler.js"));
const synthLib = require(path.join(root, "static", "improv", "synth.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));

const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases, intervals: q.intervals, roles: q.roles }));
const style = (slug) => library.styles.find((s) => s.slug === slug);
const withBass = (slug, rule) => ({ ...style(slug), bass: { ...style(slug).bass, rule } });
const withComp = (slug, voicing) => ({ ...style(slug), comp: { ...style(slug).comp, voicing } });
const pc = (m) => m % 12;
const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

function parse(text, beatsPerBar = 4, homeKey = "C") {
  const result = chart.parseChart(text, qualities, { beatsPerBar, homeKey });
  assert.equal(result.ok, true, JSON.stringify(result.error));
  return result;
}

function plan(text, st, options, beatsPerBar = 4) {
  const result = band.planBand(parse(text, beatsPerBar), typeof st === "string" ? style(st) : st, qualities, options);
  assert.equal(result.ok, true, JSON.stringify(result.error));
  return result;
}

const voice = (bar, name) => bar.events.filter((e) => e.voice === name);

// ------------------------------------------------------------------------- swing

test("straight swing moves nothing", () => {
  for (const beat of [0, 0.25, 0.5, 0.75, 1, 1.5, 3.75]) assert.ok(near(band.swingBeat(beat, 0.5), beat), `${beat}`);
});

test("swing puts the off-beat eighth at its ratio and leaves the beats alone", () => {
  assert.ok(near(band.swingBeat(0.5, 0.67), 0.67));
  assert.ok(near(band.swingBeat(1.5, 0.67), 1.67));
  assert.ok(near(band.swingBeat(0.5, 0.75), 0.75));
  for (const beat of [0, 1, 2, 3, 4]) assert.ok(near(band.swingBeat(beat, 0.67), beat));
});

test("swing moves the sixteenths in proportion and never reorders the grid", () => {
  assert.ok(near(band.swingBeat(0.25, 0.67), 0.335));
  assert.ok(near(band.swingBeat(0.75, 0.67), 0.835));
  let last = -1;
  for (let step = 0; step < 32; step++) {
    const t = band.swingBeat(step / 4, 0.7);
    assert.ok(t > last, "steps stay in order");
    last = t;
  }
});

// -------------------------------------------------------------------------- shape

test("the same chart and style give the same score every time", () => {
  const a = plan("| Dm7 | G7 | Cmaj7 | % |", "medium-swing");
  const b = plan("| Dm7 | G7 | Cmaj7 | % |", "medium-swing");
  assert.deepEqual(a, b);
});

test("one planned bar for every played bar, each knowing the written bar it came from", () => {
  const result = plan("|: Dm7 | G7 :| Cmaj7 |", "medium-swing");
  assert.equal(result.bars.length, 5);
  assert.deepEqual(
    result.bars.map((b) => b.index),
    [0, 1, 2, 3, 4],
  );
  assert.ok(result.bars.every((b) => Number.isInteger(b.source)));
});

test("every event sits inside its bar, in order, with a length and a velocity", () => {
  const result = plan("| Dm7 G7 | Cmaj7 | Am7 D7 | Gmaj7 |", "bossa-nova");
  for (const bar of result.bars) {
    let last = -1;
    for (const e of bar.events) {
      assert.ok(e.beat >= 0 && e.beat < bar.beats, `beat ${e.beat} inside the bar`);
      assert.ok(e.beat >= last, "sorted by time");
      assert.ok(e.beats > 0, "has a length");
      assert.ok(e.velocity > 0 && e.velocity <= 1, `velocity ${e.velocity}`);
      last = e.beat;
    }
  }
});

test("the band says why it cannot play instead of playing something odd", () => {
  const waltz = chart.parseChart("| C | F | G |", qualities, { beatsPerBar: 3 });
  const refused = band.planBand(waltz, style("medium-swing"), qualities);
  assert.equal(refused.ok, false);
  assert.match(refused.error, /4\/4 groove/);
  assert.match(refused.error, /3 beats/);

  assert.equal(band.planBand({ ok: false }, style("medium-swing"), qualities).ok, false);
  assert.equal(band.planBand(parse("| C |"), null, qualities).ok, false);
  assert.equal(band.planBand(parse("| C |"), withBass("medium-swing", "oompah"), qualities).ok, false);
  assert.equal(band.planBand(parse("| C |"), withComp("medium-swing", "cluster"), qualities).ok, false);
  assert.equal(band.planBand(parse("| C |"), style("medium-swing"), qualities, { swingRatio: 0.9 }).ok, false);
  assert.equal(band.planBand(parse("| C |"), style("medium-swing"), qualities, { from: 5, to: 9 }).ok, false);
});

test("a chord quality the band has no row for is named, not guessed", () => {
  const unknown = band.planBand(parse("| Cmaj7 |"), style("medium-swing"), qualities.filter((q) => q.symbol !== "maj7"));
  assert.equal(unknown.ok, false);
  assert.match(unknown.error, /maj7/);
});

// ------------------------------------------------------------------------- drums

test("drums land on the written steps, swung by the style's ratio", () => {
  const [bar] = plan("| Cmaj7 |", "medium-swing").bars;
  const ride = voice(bar, "drums").filter((e) => e.inst === "ride");
  const steps = [0, 4, 6, 8, 12, 14];
  assert.equal(ride.length, steps.length);
  steps.forEach((s, i) => assert.ok(near(ride[i].beat, band.swingBeat(s / 4, 0.62)), `step ${s}`));
  assert.ok(near(ride[2].beat, 1.62));
  assert.ok(near(ride[0].velocity, 0.8));
});

test("choosing straight takes the swing out of the same groove", () => {
  const [bar] = plan("| Cmaj7 |", "medium-swing", { swingRatio: 0.5 }).bars;
  const ride = voice(bar, "drums").filter((e) => e.inst === "ride");
  assert.ok(near(ride[2].beat, 1.5));
});

test("the beat itself is never moved by swing, so a click and the band agree", () => {
  const [bar] = plan("| Cmaj7 |", "medium-swing").bars;
  const kicks = voice(bar, "drums").filter((e) => e.inst === "kick");
  assert.deepEqual(
    kicks.map((k) => k.beat),
    [0, 1, 2, 3],
  );
});

// -------------------------------------------------------------------------- bass

test("walking: a note a beat, chord tones going up, a half step into the next chord", () => {
  const result = plan("| Dm7 | G7 | Cmaj7 | Cmaj7 |", "medium-swing");
  const [low, high] = style("medium-swing").bass.range;
  const lines = result.bars.map((b) => voice(b, "bass"));
  lines.forEach((line) => {
    assert.deepEqual(
      line.map((n) => n.beat),
      [0, 1, 2, 3],
    );
    line.forEach((n) => assert.ok(n.midi >= low && n.midi <= high));
  });
  assert.equal(pc(lines[0][0].midi), 2, "starts on the root, D");
  assert.equal(pc(lines[0][1].midi), 5, "then the third, F");
  assert.equal(pc(lines[0][2].midi), 9, "then the fifth, A");
  assert.ok([6, 8].includes(pc(lines[0][3].midi)), "then a half step from G");
  assert.ok([11, 1].includes(pc(lines[1][3].midi)), "G7 leans into C");
  assert.ok([11, 1].includes(pc(lines[2][3].midi)), "C leans into C");
  assert.ok([1, 3].includes(pc(lines[3][3].midi)), "and the last bar leans back into D when the chart loops");
  assert.equal(pc(lines[1][0].midi), 7);
  assert.ok(Math.abs(lines[1][0].midi - lines[0][3].midi) <= 1, "the new root is a half step from the approach");
});

test("walking without a loop does not lean into a chord that is not coming", () => {
  const result = plan("| Dm7 | G7 |", "medium-swing", { loop: false });
  const last = voice(result.bars[1], "bass")[3];
  assert.ok([6, 8].includes(pc(last.midi)), "G7 leans on its own root, F# or Ab");
});

test("two chords in a bar: each gets its own walking line, the first leans into the second", () => {
  const [bar] = plan("| Dm7 G7 |", "medium-swing").bars;
  const line = voice(bar, "bass");
  assert.deepEqual(
    line.map((n) => n.beat),
    [0, 1, 2, 3],
  );
  assert.equal(pc(line[0].midi), 2);
  assert.ok([6, 8].includes(pc(line[1].midi)), "approach to G");
  assert.equal(pc(line[2].midi), 7);
});

test("a slash chord puts its bass note under the chord", () => {
  const [bar] = plan("| C/E |", withBass("medium-swing", "root_fifth")).bars;
  assert.equal(pc(voice(bar, "bass")[0].midi), 4);
});

test("two-feel is a short root and a short fifth; root-fifth is the same two notes left ringing", () => {
  const short = voice(plan("| Cmaj7 |", withBass("medium-swing", "two_feel")).bars[0], "bass");
  const long = voice(plan("| Cmaj7 |", withBass("medium-swing", "root_fifth")).bars[0], "bass");
  for (const line of [short, long]) {
    assert.deepEqual(
      line.map((n) => n.beat),
      [0, 2],
    );
    assert.equal(pc(line[0].midi), 0);
    assert.equal(pc(line[1].midi), 7);
  }
  assert.ok(short[0].beats < long[0].beats);
});

test("eighths: the root on every eighth, the beats a little stronger", () => {
  const line = voice(plan("| Am |", withBass("rock-straight", "eighths")).bars[0], "bass");
  assert.equal(line.length, 8);
  assert.ok(line.every((n) => pc(n.midi) === 9));
  assert.deepEqual(
    line.map((n) => n.beat),
    [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5],
  );
  assert.ok(line[0].velocity > line[1].velocity);
});

test("bossa: root, then the fifth on the and of two, twice a bar", () => {
  const line = voice(plan("| Dm7 |", "bossa-nova").bars[0], "bass");
  assert.deepEqual(
    line.map((n) => n.beat),
    [0, 1.5, 2, 3.5],
  );
  assert.deepEqual(
    line.map((n) => pc(n.midi)),
    [2, 9, 2, 9],
  );
});

test("boogie walks root, third, fifth, sixth, flat seven and back, with the third of the chord", () => {
  const major = voice(plan("| C7 |", "blues-shuffle").bars[0], "bass");
  assert.deepEqual(
    major.map((n) => n.midi - major[0].midi),
    [0, 4, 7, 9, 10, 9, 7, 4],
  );
  const minor = voice(plan("| Cm7 |", "blues-shuffle").bars[0], "bass");
  assert.deepEqual(
    minor.map((n) => n.midi - minor[0].midi),
    [0, 3, 7, 9, 10, 9, 7, 3],
  );
  assert.deepEqual(
    major.map((n) => Number(n.beat.toFixed(2))),
    [0, 0.67, 1, 1.67, 2, 2.67, 3, 3.67],
    "the shuffle is the swing, nothing else",
  );
});

test("bass notes stay inside the style's range for every rule and every root", () => {
  const rules = band.BASS_RULES;
  const roots = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];
  for (const rule of rules) {
    const st = withBass("medium-swing", rule);
    const [low, high] = st.bass.range;
    const text = "| " + roots.map((r) => `${r}7`).join(" | ") + " |";
    for (const bar of plan(text, st).bars) {
      for (const n of voice(bar, "bass")) assert.ok(n.midi >= low && n.midi <= high, `${rule} ${n.midi}`);
    }
  }
});

// -------------------------------------------------------------------------- comp

const compAt = (bar, beat) => voice(bar, "comp").filter((e) => near(e.beat, beat));

test("shell voicing: the third, the seventh and the ninth, inside the register", () => {
  const result = plan("| Dm7 | G7 | Cmaj7 |", "medium-swing");
  const [low, high] = style("medium-swing").comp.register;
  const sets = result.bars.map((b) => new Set(compAt(b, 0).map((e) => pc(e.midi))));
  assert.deepEqual([...sets[0]].sort((a, b) => a - b), [0, 4, 5], "Dm7: C, E, F");
  assert.deepEqual([...sets[1]].sort((a, b) => a - b), [5, 9, 11], "G7: F, A, B");
  assert.deepEqual([...sets[2]].sort((a, b) => a - b), [2, 4, 11], "Cmaj7: E, B, D");
  for (const bar of result.bars) for (const e of voice(bar, "comp")) assert.ok(e.midi >= low && e.midi <= high);
});

test("voices move the shortest way from one chord to the next", () => {
  const result = plan("| Dm7 | G7 | Cmaj7 |", "medium-swing");
  const chords = result.bars.map((b) =>
    compAt(b, 0)
      .map((e) => e.midi)
      .sort((a, b) => a - b),
  );
  for (let i = 1; i < chords.length; i++) {
    const moved = chords[i].reduce((sum, m, j) => sum + Math.abs(m - chords[i - 1][j]), 0);
    assert.ok(moved <= 8, `chord ${i} moved ${moved} semitones in total`);
  }
});

test("a repeated chord is played with the same notes, not a new inversion", () => {
  const result = plan("| Dm7 | % | % |", "medium-swing");
  const notes = result.bars.map((b) => compAt(b, 0).map((e) => e.midi));
  assert.deepEqual(notes[0], notes[1]);
  assert.deepEqual(notes[0], notes[2]);
});

test("a comping hit that crosses a chord change is cut and restarted on the new chord", () => {
  const [bar] = plan("| Dm7 G7 |", "medium-swing").bars;
  const second = voice(bar, "comp").filter((e) => e.beat >= 1.4);
  const dm = second.filter((e) => e.beat < 2 - 1e-9);
  const g = second.filter((e) => near(e.beat, 2));
  assert.ok(dm.length > 0 && g.length > 0, "the tail of Dm7 and the start of G7");
  assert.ok(dm.every((e) => e.beat + e.beats <= 2 + 1e-9), "Dm7 stops where G7 starts");
  assert.deepEqual(new Set(g.map((e) => pc(e.midi))), new Set([5, 9, 11]));
});

test("triad voicing is the root, the third and the fifth", () => {
  const sets = plan("| C | Am |", "pop-ballad").bars.map((b) => [...new Set(compAt(b, 0).map((e) => pc(e.midi)))].sort((a, c) => a - c));
  assert.deepEqual(sets[0], [0, 4, 7]);
  assert.deepEqual(sets[1], [0, 4, 9]);
});

test("seventh voicing is the four notes of the chord, thinned for the big ones", () => {
  const sets = plan("| Cmaj7 | C7 | C13 |", "blues-shuffle").bars.map((b) => compAt(b, 0).map((e) => pc(e.midi)));
  assert.deepEqual([...new Set(sets[0])].sort((a, b) => a - b), [0, 4, 7, 11]);
  assert.deepEqual([...new Set(sets[1])].sort((a, b) => a - b), [0, 4, 7, 10]);
  assert.ok(sets[2].length <= 4, "a thirteenth chord is thinned to four notes");
  assert.ok(sets[2].includes(10) && sets[2].includes(4), "and keeps the third and the seventh");
});

test("shell voicing leaves out a color tone that would clash", () => {
  const sets = plan("| G7b9 | Dm7b5 | Csus4 |", "medium-swing").bars.map((b) => new Set(compAt(b, 0).map((e) => pc(e.midi))));
  assert.deepEqual([...sets[0]].sort((a, b) => a - b), [5, 11], "G7b9: B and F, no natural 9");
  assert.deepEqual([...sets[1]].sort((a, b) => a - b), [0, 5], "Dm7b5: F and C");
  assert.ok(!sets[2].has(4), "a sus chord does not get its third");
});

// ----------------------------------------------------------------- loop and range

test("a bar range plays only those bars and leans into its own first chord", () => {
  const text = "| Dm7 | G7 | Cmaj7 | Am7 |";
  const result = plan(text, "medium-swing", { from: 1, to: 3 });
  assert.equal(result.bars.length, 2);
  const lastBass = voice(result.bars[1], "bass")[3];
  assert.ok([6, 8].includes(pc(lastBass.midi)), "Cmaj7 leans back into G, the first bar of the range");
});

// ------------------------------------------------------------------ the whole library

const KEYS = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];

for (const p of library.progressions) {
  const st = style(p.default_style);

  test(`${p.slug} plays in ${st.name}, in every key, inside the style's ranges`, () => {
    const beatsPerBar = Number(p.time_signature.split("/")[0]);
    const parsed = chart.parseChart(p.chart, qualities, { beatsPerBar, homeKey: p.home_key });
    for (const key of KEYS) {
      const moved = chart.transposeToKey(parsed, p.home_key, key);
      const result = band.planBand(moved, st, qualities);
      assert.equal(result.ok, true, JSON.stringify(result.error));
      assert.equal(result.bars.length, parsed.bars.length);
      for (const bar of result.bars) {
        assert.ok(voice(bar, "drums").length > 0, "drums play every bar");
        assert.ok(voice(bar, "bass").length > 0, "bass plays every bar");
        assert.ok(voice(bar, "comp").length > 0, "comp plays every bar");
        for (const n of voice(bar, "bass")) assert.ok(n.midi >= st.bass.range[0] && n.midi <= st.bass.range[1], `bass ${n.midi} in ${key}`);
        for (const n of voice(bar, "comp")) assert.ok(n.midi >= st.comp.register[0] && n.midi <= st.comp.register[1], `comp ${n.midi} in ${key}`);
      }
    }
  });
}

test("the six starter styles cover jazz, blues, latin, pop, rock and gospel, and each one can play", () => {
  assert.deepEqual(
    new Set(library.styles.map((s) => s.genre)),
    new Set(["jazz", "blues", "latin", "pop", "rock", "gospel"]),
  );
  for (const st of library.styles) {
    const result = plan("| Dm7 | G7 | Cmaj7 | % |", st);
    assert.equal(result.bars.length, 4);
  }
});

test("the band's lists are the lists the server validates against", () => {
  assert.deepEqual(band.DRUM_INSTRUMENTS.length, 8);
  assert.ok(band.BASS_RULES.includes("walking") && band.VOICINGS.includes("shell"));
});

// ---------------------------------------------------------------------- scheduler

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
  // Move the clock forward, firing timers in order on the way.
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

function tinyPlan(bars = 2, beats = 4) {
  return {
    ok: true,
    beatsPerBar: beats,
    bars: Array.from({ length: bars }, (_, index) => ({
      index,
      beats,
      events: [
        { voice: "drums", inst: "kick", beat: 0, beats: 0.25, velocity: 1 },
        { voice: "bass", beat: 1, beats: 1, midi: 40 + index, velocity: 1 },
        { voice: "drums", inst: "hat", beat: 2.5, beats: 0.25, velocity: 1 },
      ],
    })),
  };
}

function harness(extra) {
  const world = fakeWorld();
  const heard = [];
  const bars = [];
  const s = scheduler.createScheduler({
    now: world.now,
    setTimer: world.setTimer,
    clearTimer: world.clearTimer,
    onEvent: (event, when, seconds) => heard.push({ event, when, seconds, queuedAt: world.t }),
    onBar: (index, start, pass) => bars.push({ index, start, pass }),
    ...extra,
  });
  return { world, s, heard, bars };
}

test("events are queued on the audio clock ahead of time, never in the past", () => {
  const { world, s, heard } = harness();
  s.start(tinyPlan(4), { bpm: 120, at: 100.5 });
  world.run(10);
  assert.ok(heard.length > 0);
  for (const h of heard) assert.ok(h.when >= h.queuedAt, `queued ${h.queuedAt} for ${h.when}`);
});

test("bars start exactly one bar apart and events sit at their beat inside them", () => {
  const { world, s, heard, bars } = harness();
  s.start(tinyPlan(4), { bpm: 120, at: 100.5 });
  world.run(8);
  const starts = bars.slice(0, 4).map((b) => b.start);
  starts.forEach((t, k) => assert.ok(near(t, 100.5 + 2 * k), `bar ${k} at ${t}`));
  const firstBar = heard.filter((h) => h.when < 102.5);
  const kick = firstBar.find((h) => h.event.inst === "kick");
  const bass = firstBar.find((h) => h.event.voice === "bass");
  const hat = firstBar.find((h) => h.event.inst === "hat");
  assert.ok(near(kick.when, 100.5));
  assert.ok(near(bass.when, 101.0), "beat 1 at 120 bpm is half a second in");
  assert.ok(near(hat.when, 101.75), "beat 2.5 is 1.25 seconds in");
  assert.ok(near(bass.seconds, 0.5), "a one-beat note lasts half a second");
});

test("a timer that runs late does not move the beat", () => {
  const steady = harness();
  steady.s.start(tinyPlan(4), { bpm: 90, at: 100.5 });
  steady.world.run(12);
  const sloppy = harness({ intervalMs: 90 });
  sloppy.s.start(tinyPlan(4), { bpm: 90, at: 100.5 });
  sloppy.world.run(12);
  const times = (h) => h.heard.slice(0, 20).map((x) => Number(x.when.toFixed(9)));
  assert.deepEqual(times(sloppy), times(steady));
});

test("looping goes back to the first bar and counts the passes", () => {
  const { world, s, bars } = harness();
  s.start(tinyPlan(3), { bpm: 240, at: 100.1 });
  world.run(6);
  assert.deepEqual(
    bars.slice(0, 7).map((b) => [b.index, b.pass]),
    [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1], [0, 2]],
  );
  assert.equal(s.running, true);
});

test("without a loop it plays once, says it is done once, and goes quiet", () => {
  let ended = 0;
  const { world, s, heard } = harness({ onEnd: () => ended++ });
  s.start(tinyPlan(2), { bpm: 120, loop: false, at: 100.2 });
  world.run(10);
  assert.equal(ended, 1);
  assert.equal(s.running, false);
  assert.equal(heard.length, 6);
  assert.equal(world.timers.length, 0, "no timer left running");
});

test("a tempo change waits for the next bar line and leaves no gap or overlap", () => {
  const { world, s, bars } = harness();
  s.start(tinyPlan(4), { bpm: 120, at: 100.2 });
  world.run(1.0);
  s.setBpm(60);
  world.run(20);
  const lengths = [];
  for (let k = 1; k < 5; k++) lengths.push(Number((bars[k].start - bars[k - 1].start).toFixed(6)));
  assert.deepEqual(lengths, [2, 4, 4, 4], "the bar already queued keeps its old length, every later bar uses the new tempo");
});

test("barAt tells the screen where the music is", () => {
  const { world, s } = harness();
  s.start(tinyPlan(2), { bpm: 120, at: 100.5 });
  world.run(2.4);
  const here = s.barAt(101.0);
  assert.equal(here.index, 0);
  assert.ok(near(here.beat, 1));
  const next = s.barAt(102.75);
  assert.equal(next.index, 1);
  assert.ok(near(next.beat, 0.5));
  assert.equal(s.barAt(99), null);
});

test("stop silences it at once", () => {
  const { world, s, heard } = harness();
  s.start(tinyPlan(4), { bpm: 120, at: 100.1 });
  world.run(1);
  s.stop();
  const count = heard.length;
  world.run(10);
  assert.equal(heard.length, count);
  assert.equal(s.running, false);
});

test("after the page stalls the band restarts on the next bar, not in a burst of old notes", () => {
  const { world, s, heard, bars } = harness();
  s.start(tinyPlan(4), { bpm: 120, at: 100.1 });
  world.run(1);
  world.t += 30;
  world.timers.forEach((t) => (t.at = world.t));
  const before = heard.length;
  world.run(1);
  assert.ok(s.lateBars >= 1);
  for (const h of heard.slice(before)) assert.ok(h.when >= h.queuedAt, "nothing is queued in the past");
  assert.ok(bars[bars.length - 1].start > 130);
});

test("tempo is held to what a person can play along with", () => {
  const { s } = harness();
  s.start(tinyPlan(1), { bpm: 5000 });
  assert.equal(s.bpm, scheduler.MAX_BPM);
  s.setBpm(1);
  assert.equal(s.bpm, scheduler.MIN_BPM);
  s.stop();
});

test("scheduling a real plan queues every event of every bar once per pass", () => {
  const result = plan("| Dm7 | G7 | Cmaj7 | % |", "medium-swing");
  const perPass = result.bars.reduce((n, b) => n + b.events.length, 0);
  const { world, s, heard } = harness();
  s.start(result, { bpm: 240, loop: false, at: 100.1 });
  world.run(10);
  assert.equal(heard.length, perPass);
});

// -------------------------------------------------------------------------- synth

function fakeAudio() {
  const nodes = [];
  const param = (initial = 0) => {
    const p = { value: initial, calls: [] };
    const check = (v, t) => {
      if (!Number.isFinite(v) || !Number.isFinite(t)) throw new RangeError(`bad automation ${v} at ${t}`);
      if (t < 0) throw new RangeError("negative time");
    };
    p.setValueAtTime = (v, t) => (check(v, t), p.calls.push(["set", v, t]), p);
    p.linearRampToValueAtTime = (v, t) => (check(v, t), p.calls.push(["lin", v, t]), p);
    p.exponentialRampToValueAtTime = (v, t) => {
      check(v, t);
      if (!(v > 0)) throw new RangeError("an exponential ramp needs a positive target");
      p.calls.push(["exp", v, t]);
      return p;
    };
    return p;
  };
  const make = (kind, fields) => {
    const n = { kind, to: [], started: null, stopped: null, connect(x) { n.to.push(x); return x; }, start(t) { n.started = t; }, stop(t) { n.stopped = t; }, ...fields };
    nodes.push(n);
    return n;
  };
  const ctx = {
    currentTime: 10,
    sampleRate: 8000,
    destination: make("destination"),
    createGain: () => make("gain", { gain: param(1) }),
    createOscillator: () => make("osc", { type: "sine", frequency: param(440) }),
    createBiquadFilter: () => make("filter", { type: "lowpass", frequency: param(350), Q: param(1) }),
    createBufferSource: () => make("source", { buffer: null, loop: false }),
    createBuffer: (channels, length) => ({ length, getChannelData: () => new Float32Array(length) }),
    createDynamicsCompressor: () => make("limiter", { threshold: param(), knee: param(), ratio: param(), attack: param(), release: param() }),
  };
  return { ctx, nodes };
}

const sound = (nodes) => nodes.filter((n) => n.kind === "osc" || n.kind === "source");

test("midi notes become the right frequencies", () => {
  assert.ok(near(synthLib.midiToHz(69), 440));
  assert.ok(near(synthLib.midiToHz(57), 220));
  assert.ok(Math.abs(synthLib.midiToHz(60) - 261.6256) < 0.001);
});

test("the synth ends in the limiter and then the speakers", () => {
  const { ctx, nodes } = fakeAudio();
  synthLib.createSynth(ctx);
  const limiter = nodes.find((n) => n.kind === "limiter");
  assert.ok(limiter.to.includes(ctx.destination));
});

test("every drum voice, the bass and the comp make sound that starts on time and ends", () => {
  const cases = [
    ...band.DRUM_INSTRUMENTS.map((inst) => ({ voice: "drums", inst, velocity: 0.7 })),
    { voice: "bass", midi: 40, velocity: 0.8 },
    { voice: "comp", midi: 64, velocity: 0.6 },
  ];
  for (const event of cases) {
    const { ctx, nodes } = fakeAudio();
    const synth = synthLib.createSynth(ctx);
    const before = sound(nodes).length;
    synth.play(event, 12.5, 0.5);
    const made = sound(nodes).slice(before);
    assert.ok(made.length > 0, `${event.voice} ${event.inst || ""} makes sound`);
    for (const n of made) {
      assert.ok(near(n.started, 12.5), "starts when asked");
      assert.ok(n.stopped > n.started, "and is told to stop, so nothing leaks");
    }
  }
});

test("the comp plays the note it was given", () => {
  const { ctx, nodes } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  synth.play({ voice: "comp", midi: 69, velocity: 0.6 }, 11, 1);
  const body = nodes.find((n) => n.kind === "osc" && n.frequency.calls.some((c) => near(c[1], 440)));
  assert.ok(body, "an oscillator at 440 Hz");
});

test("a note for a time already gone is heard now, not dropped", () => {
  const { ctx, nodes } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  synth.play({ voice: "bass", midi: 40, velocity: 0.8 }, 3, 0.5);
  const first = sound(nodes)[0];
  assert.ok(near(first.started, ctx.currentTime));
});

test("a velocity of nothing cannot break the envelope", () => {
  const { ctx } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  assert.doesNotThrow(() => synth.play({ voice: "drums", inst: "kick", velocity: 0 }, 11, 0.1));
  assert.doesNotThrow(() => synth.play({ voice: "comp", midi: 60 }, 11, 0.1));
});

test("an unknown voice or drum is ignored, not a crash in the middle of a take", () => {
  const { ctx, nodes } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  const before = sound(nodes).length;
  synth.play({ voice: "theremin", midi: 60, velocity: 1 }, 11, 1);
  synth.play({ voice: "drums", inst: "cowbell", velocity: 1 }, 11, 1);
  assert.equal(sound(nodes).length, before);
});

test("each part has its own level and mute, so the comping can be silenced to hear your own harmony", () => {
  const { ctx, nodes } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  const gains = nodes.filter((n) => n.kind === "gain").slice(1, 4);
  const [drums, bass, comp] = gains;
  synth.setMuted("comp", true);
  assert.equal(comp.gain.value, 0);
  assert.notEqual(bass.gain.value, 0);
  synth.setMuted("comp", false);
  assert.ok(comp.gain.value > 0);
  synth.setLevel("drums", 5);
  assert.equal(drums.gain.value, 1, "levels are held between 0 and 1");
  synth.setLevel("drums", 0.25);
  synth.setMuted("drums", true);
  synth.setMuted("drums", false);
  assert.equal(drums.gain.value, 0.25, "unmuting brings back the level that was set");
  assert.deepEqual(synth.groups, ["drums", "bass", "comp", "click"]);
});

test("a whole planned bar goes through the synth without a single bad automation value", () => {
  const { ctx } = fakeAudio();
  const synth = synthLib.createSynth(ctx);
  for (const st of library.styles) {
    for (const bar of plan("| Dm7 G7 | Cmaj7 | Am7b5 D7alt |", st).bars) {
      for (const e of bar.events) assert.doesNotThrow(() => synth.play(e, 11 + e.beat * 0.5, e.beats * 0.5));
    }
  }
});
