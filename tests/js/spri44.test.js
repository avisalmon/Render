// SPR-I.4.4 improv: saved takes and replay over the same band. The band and the judge are
// already proved; what is proved here is that a take is replayed from its own snapshot and
// nothing else, that its notes come back as notes to sound, and the small rules of the list.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const T = require(path.join(root, "static", "improv", "takes.js"));
const P = require(path.join(root, "static", "improv", "play.js"));
const M = require(path.join(root, "static", "improv", "midi.js"));
const S = require(path.join(root, "static", "improv", "setup.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));

const qualities = theory.chord_qualities;
const styles = library.styles.map((s, i) => ({ ...s, id: i + 1 }));

const take = {
  id: 7,
  progression: 3,
  style: styles.find((s) => s.time_signature === "4/4").id,
  chart: "| Dm7 | G7 | Cmaj7 | % |",
  home_key: "C",
  key: "Eb",
  time_signature: "4/4",
  tempo: 120,
  swing_ratio: "0.67",
  loop_from: 1,
  loop_to: 3,
  bars: 2,
  started_at: "2026-10-05T14:05:00",
  duration_ms: 4000,
  events: [
    { t_ms: 0, type: "on", note: 65, velocity: 90 },
    { t_ms: 400, type: "off", note: 65, velocity: 0 },
    { t_ms: 500, type: "on", note: 67, velocity: 127 },
    { t_ms: 500, type: "on", note: 60, velocity: 0 },
    { t_ms: 1500, type: "off", note: 67, velocity: 0 },
    { t_ms: 2000, type: "off", note: 99, velocity: 0 },
  ],
  score: null,
  metrics: { notes: 3, chordTonePct: 67, outsidePct: 33, meanOffsetMs: -18 },
  judge_version: 1,
  is_kept: true,
};

// ------------------------------------------------------------- the same band again

test("a take is replayed as the chart it carries, in the key and bars it was played", () => {
  const settings = T.replaySettings(take);
  assert.equal(settings.key, "Eb");
  assert.equal(settings.first, "2", "bars are typed 1-based on the Play screen");
  assert.equal(settings.last, "3");
  assert.equal(settings.swing, "swing");
  assert.equal(settings.countIn, T.REPLAY_COUNT_IN, "one bar to hear where the beat is");
  assert.equal(T.replaySettings({ ...take, swing_ratio: "0.50" }).swing, "straight");
});

test("the replay plan builds from the snapshot alone, with the band the take names", () => {
  const style = styles.find((s) => s.id === take.style);
  const built = P.buildPlan({ progression: T.replayProgression(take, "ii-V-I"), style, qualities, settings: T.replaySettings(take) });
  assert.equal(built.ok, true, built.error);
  assert.equal(built.key, "Eb");
  assert.equal(built.from, 1);
  assert.equal(built.to, 3);
  assert.equal(built.countInBars, 1);
  assert.equal(built.chart.bars[1].chords[0].name, "Bb7", "G7 played in Eb is Bb7");
});

test("a deleted progression does not stop a replay, because nothing is read from it", () => {
  const style = styles.find((s) => s.id === take.style);
  const gone = { ...take, progression: null };
  const built = P.buildPlan({ progression: T.replayProgression(gone), style, qualities, settings: T.replaySettings(gone) });
  assert.equal(built.ok, true);
  assert.equal(T.replayProgression(gone).title, "Free chart");
});

// ---------------------------------------------------------------- notes to sound

test("note-ons are paired with their note-offs into notes to sound", () => {
  const spans = T.noteSpans(take.events);
  assert.deepEqual(spans.map((s) => [s.note, s.atMs, s.seconds]), [
    [65, 0, 0.4],
    [60, 500, 0.5],
    [67, 500, 1],
  ]);
  assert.equal(spans[2].velocity, 1, "127 is as loud as it goes");
  assert.equal(spans[1].velocity, 0.05, "a velocity of nought still sounds, faintly");
});

test("a note never let go is held for a moment, and a note-off for nothing is nothing", () => {
  const spans = T.noteSpans([{ t_ms: 0, type: "on", note: 60, velocity: 80 }, { t_ms: 10, type: "off", note: 61, velocity: 0 }]);
  assert.deepEqual(spans.map((s) => [s.note, s.seconds]), [[60, 0.5]]);
  assert.deepEqual(T.noteSpans([]), []);
  assert.deepEqual(T.noteSpans(null), []);
  assert.deepEqual(T.noteSpans([null, { type: "on" }]), []);
});

test("a note held for an hour is not held for an hour", () => {
  const spans = T.noteSpans([{ t_ms: 0, type: "on", note: 60, velocity: 80 }, { t_ms: 3600000, type: "off", note: 60, velocity: 0 }]);
  assert.equal(spans[0].seconds, 20);
});

test("each note is placed on the audio clock from the first judged downbeat", () => {
  const placed = T.scheduleAt(T.noteSpans(take.events), 12.5);
  assert.deepEqual(placed.map((s) => s.when), [12.5, 13.0, 13.0]);
});

test("the replay runs to the last note and a bar more, never shorter than the take", () => {
  assert.equal(T.replayBars(take, T.noteSpans(take.events)), 3, "two bars of take, the notes end in bar 1, plus one");
  const long = { ...take, events: [{ t_ms: 7000, type: "on", note: 60, velocity: 80 }, { t_ms: 7500, type: "off", note: 60, velocity: 0 }] };
  assert.equal(T.replayBars(long, T.noteSpans(long.events)), 5, "a note in bar 4 means four bars plus one");
});

// ----------------------------------------------------------------- MIDI bytes

test("a note out is the same bytes as a note in", () => {
  assert.deepEqual([...M.noteOnBytes(60, 90)], [0x90, 60, 90]);
  assert.deepEqual([...M.noteOffBytes(60)], [0x80, 60, 0]);
  assert.deepEqual(M.parse(M.noteOnBytes(62, 100)), { type: "on", note: 62, velocity: 100 });
  assert.deepEqual(M.parse(M.noteOffBytes(62)), { type: "off", note: 62 });
  assert.deepEqual([...M.noteOnBytes(60, 0.5)], [0x90, 60, 64], "a velocity of 0 to 1 is scaled");
  assert.deepEqual([...M.noteOnBytes(60, 500)], [0x90, 60, 127], "and never past the top");
});

// ------------------------------------------------------------- where it sounds

test("the piano's own output is the one with the piano's name, else the first plugged in", () => {
  const outs = S.inputChoices([{ id: "o1", name: "Minilab", state: "connected" }, { id: "o2", name: "Clavinova", state: "connected" }]);
  assert.equal(S.pickOutput(outs, "Clavinova").id, "o2");
  assert.equal(S.pickOutput(outs, "Nothing like it").id, outs[0].id, "the first in the list as it is shown");
  assert.equal(S.pickOutput([], "Clavinova"), null);
  assert.equal(S.pickOutput(S.inputChoices([{ id: "o2", name: "Clavinova", state: "disconnected" }]), "Clavinova"), null);
});

// ------------------------------------------------------------------- the list

test("a take is described for the list in words, newest first", () => {
  const d = T.describe(take, { titles: { 3: "ii-V-I in major" }, now: "2026-10-05T18:00:00" });
  assert.equal(d.title, "ii-V-I in major");
  assert.equal(d.when, "Today 14:05");
  assert.equal(d.summary, "Eb, 120 bpm, swing, 2 bars");
  assert.equal(d.notes, 3);
  assert.equal(d.verdict, "67% chord tones, 33% outside, rushing by 18 ms");
  assert.equal(d.kept, true);
  assert.equal(T.describe({ ...take, progression: null }, {}).title, "Free chart");
  assert.equal(T.describe({ ...take, score: 85, metrics: { chordTonePct: 90, meanOffsetMs: 2 } }, {}).verdict, "score 85, 90% chord tones, on the beat");
  assert.equal(T.describe({ ...take, metrics: {}, events: [] }, {}).verdict, "no notes");
});

test("when is today, yesterday, or the date", () => {
  assert.equal(T.formatWhen("2026-10-04T09:30:00", "2026-10-05T18:00:00"), "Yesterday 09:30");
  assert.equal(T.formatWhen("2026-09-30T23:59:00", "2026-10-05T18:00:00"), "2026-09-30 23:59");
  assert.equal(T.formatWhen("junk", "2026-10-05T18:00:00"), "");
});

test("the list is newest first", () => {
  const a = { ...take, id: 1, started_at: "2026-10-01T10:00:00" };
  const b = { ...take, id: 2, started_at: "2026-10-03T10:00:00" };
  assert.deepEqual(T.order([a, b]).map((t) => t.id), [2, 1]);
});
