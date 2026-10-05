// SPR-I.5.1 improv: lessons. What is proved here is the part with no page in it: tracks in the order
// a player meets them, the explanation turned into text blocks and nothing else, a demo phrase moved
// to the key it is played in and swung like the band, and the rules for when a take counts for an exercise.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const L = require(path.join(root, "static", "improv", "lessons.js"));
const P = require(path.join(root, "static", "improv", "play.js"));
const J = require(path.join(root, "static", "improv", "judge.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));

const lesson = (slug, track, order, extra) => ({ slug, track, order, title: slug, level: 1, status: "published", prerequisite: null, ...extra });

test("the tracks are in the order the Python knows them in", () => {
  const py = fs.readFileSync(path.join(root, "improv", "teaching.py"), "utf8");
  const block = /TRACK_ORDER = \[([\s\S]*?)\]/.exec(py)[1];
  const slugs = [...block.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(L.TRACKS.map((t) => t[0]), slugs);
});

test("lessons are grouped by track in teaching order, by position, and an empty track is left out", () => {
  const groups = L.groupByTrack([lesson("b", "guide_tones", 2), lesson("a", "guide_tones", 1), lesson("c", "chord_tones", 1)]);
  assert.deepEqual(groups.map((g) => g.track), ["chord_tones", "guide_tones"]);
  assert.deepEqual(groups[1].lessons.map((l) => l.slug), ["a", "b"]);
  assert.equal(groups[0].label, "Chord tones");
});

test("a track the page does not know is shown under Other rather than lost", () => {
  const groups = L.groupByTrack([lesson("x", "something_new", 1)]);
  assert.equal(groups[0].label, "Other");
  assert.equal(groups[0].lessons.length, 1);
});

test("the small line names the level, the lesson before it and a draft", () => {
  const first = lesson("chord-tones", "chord_tones", 1, { title: "Chord tones over ii-V-I" });
  const second = lesson("guide", "guide_tones", 1, { level: 2, prerequisite: "chord-tones", status: "draft" });
  assert.equal(L.describe(first, [first, second]), "Level 1.");
  assert.equal(L.describe(second, [first, second]), "Level 2, after Chord tones over ii-V-I, draft, only you can see it.");
});

test("a lesson no person has read says so", () => {
  assert.match(L.authorshipNote({ authorship: "ai_drafted" }), /not yet read/);
  assert.match(L.authorshipNote({ authorship: "reviewed" }), /read and corrected/);
  assert.equal(L.authorshipNote({ authorship: "avi_written" }), "");
});

test("the explanation becomes headings, paragraphs and lists, with bold, italic and code kept as styles", () => {
  const blocks = L.parseText("## Why\nPlay the **third** and the *seventh*.\nSecond line of it.\n\n- one\n- two with `Dm7`\n\n1. first\n2. second");
  assert.deepEqual(blocks.map((b) => b.type), ["h", "p", "ul", "ol"]);
  assert.equal(blocks[0].level, 2);
  assert.equal(blocks[0].text, "Why");
  assert.deepEqual(blocks[1].inlines.map((i) => i.style), [null, "strong", null, "em", null]);
  assert.equal(blocks[1].inlines.map((i) => i.text).join(""), "Play the third and the seventh. Second line of it.");
  assert.equal(blocks[2].items.length, 2);
  assert.deepEqual(blocks[2].items[1].map((i) => i.style), [null, "code"]);
  assert.equal(blocks[3].items.length, 2);
});

test("markup in an explanation stays text: nothing is parsed as a tag", () => {
  const blocks = L.parseText('<script>alert(1)</script> and <b>bold</b>\n\n- <img src=x onerror=alert(1)>');
  const all = JSON.stringify(blocks);
  assert.ok(all.includes("<script>alert(1)</script>"));
  assert.deepEqual(blocks.map((b) => b.type), ["p", "ul"]);
  for (const b of blocks) for (const part of b.inlines || b.items.flat()) assert.ok(["strong", "em", "code", null].includes(part.style));
});

test("an empty explanation is no blocks, and Windows line ends read the same as Unix ones", () => {
  assert.deepEqual(L.parseText(""), []);
  assert.deepEqual(L.parseText(null), []);
  assert.deepEqual(L.parseText("a\r\n\r\nb"), L.parseText("a\n\nb"));
});

test("a phrase moves the short way round from the key it was written in", () => {
  assert.equal(L.transposeBy("C", "C"), 0);
  assert.equal(L.transposeBy("C", "D"), 2);
  assert.equal(L.transposeBy("C", "Bb"), -2);
  assert.equal(L.transposeBy("C", "F#"), 6);
  assert.equal(L.transposeBy("C", "Gb"), 6);
  assert.equal(L.transposeBy("Eb", "C"), -3);
  assert.equal(L.transposeBy("C", "nonsense"), 0);
});

const phrase = {
  written_in_key: "C",
  length_beats: 4,
  notes: [
    { midi: 62, beat: 0, length: 1, velocity: 90 },
    { midi: 65, beat: 1.5, length: 0.5, velocity: 127 },
    { midi: 69, beat: 2, length: 2, velocity: 1 },
  ],
};

test("a demo phrase sounds at the beat it is written on, in the key it is played in", () => {
  const notes = L.demoNotes(phrase, { playedKey: "C", bpm: 120, swingRatio: 0.5, downbeat: 10 });
  assert.deepEqual(notes.map((n) => n.note), [62, 65, 69]);
  assert.equal(notes[0].when, 10);
  assert.ok(Math.abs(notes[1].when - (10 + 1.5 * 0.5)) < 1e-9);
  assert.ok(Math.abs(notes[2].seconds - 1) < 1e-9);
  const up = L.demoNotes(phrase, { playedKey: "D", bpm: 120, swingRatio: 0.5, downbeat: 0 });
  assert.deepEqual(up.map((n) => n.note), [64, 67, 71]);
});

test("the demo swings the way the band swings, so an off-beat eighth lands where the band's does", () => {
  const straight = L.demoNotes(phrase, { playedKey: "C", bpm: 60, swingRatio: 0.5, downbeat: 0 });
  const swung = L.demoNotes(phrase, { playedKey: "C", bpm: 60, swingRatio: 0.67, downbeat: 0 });
  assert.ok(Math.abs(straight[1].when - 1.5) < 1e-9);
  assert.ok(Math.abs(swung[1].when - 1.67) < 1e-9);
  assert.equal(swung[0].when, 0);
  assert.equal(swung[2].when, 2);
});

test("a note's loudness is 0 to 1 and never silent, and a note never leaves the keyboard", () => {
  const notes = L.demoNotes({ written_in_key: "C", notes: [{ midi: 126, beat: 0, length: 1, velocity: 127 }, { midi: 1, beat: 1, length: 1, velocity: 1 }] }, { playedKey: "F#", bpm: 100, downbeat: 0 });
  assert.equal(notes[0].note, 127);
  assert.equal(notes[0].velocity, 1);
  assert.ok(notes[1].velocity >= 0.05);
  assert.ok(notes[1].note >= 0);
});

test("the demo is heard over as many bars as it lasts, from bar one, and never past the chart", () => {
  const progression = { home_key: "C" };
  assert.deepEqual(L.hearSettings({ length_beats: 4 }, progression, 8, 4, "swing"), { key: "C", countIn: 1, first: "1", last: "1", swing: "swing", metronome: false });
  assert.equal(L.hearSettings({ length_beats: 6 }, progression, 8, 4).last, "2");
  assert.equal(L.hearSettings({ length_beats: 64 }, progression, 4, 4).last, "4");
  assert.equal(L.hearSettings({ length_beats: 64 }, progression, 40, 4).last, "16");
  assert.equal(L.hearSettings(null, progression, 8, 4).last, "1");
  assert.equal(L.hearSettings({ length_beats: 9 }, progression, 8, 3).last, "3");
});

test("an exercise says what it asks in one line and links to Play by slug", () => {
  assert.equal(L.exerciseLine({ bars: 4, key: "C", tempo: 80, pass_score: 70, xp: 10 }), "4 bars in C at 80 bpm. Pass at 70, worth 10 XP.");
  assert.equal(L.exerciseLine({ bars: 1, key: "Bb", tempo: 60, pass_score: 60, xp: 5 }), "1 bar in Bb at 60 bpm. Pass at 60, worth 5 XP.");
  assert.equal(L.exerciseUrl("/improv/play/", "chord tones/1"), "/improv/play/?exercise=chord%20tones%2F1");
});

// ------------------------------------------------------------- Play opened for an exercise

const exercise = { slug: "e", progression: 3, bars: 4, pass_score: 70, scoring_kind: "chord_tones_on_beats", scoring_params: { beats: [1, 3] } };
const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));
const styles = library.styles.map((s, i) => ({ ...s, id: i + 1 }));

function built(from, to, bars, extra) {
  return { ok: true, from, to, metronome: false, chart: { bars: new Array(bars).fill(0) }, ...extra };
}

test("an exercise is scored the way it asks, and a kind the judge does not score is free play", () => {
  assert.deepEqual(P.exerciseScoring(exercise, J.SCORING_KINDS), { kind: "chord_tones_on_beats", params: { beats: [1, 3] } });
  assert.deepEqual(P.exerciseScoring({ ...exercise, scoring_kind: "comping_voicings" }, J.SCORING_KINDS), { kind: "free_play", params: {} });
  assert.deepEqual(P.exerciseScoring(null, J.SCORING_KINDS), { kind: "free_play", params: {} });
  assert.deepEqual(P.exerciseScoring({ ...exercise, scoring_params: null }, J.SCORING_KINDS).params, {});
});

test("the kinds the Python scores are the kinds the judge scores", () => {
  const model = fs.readFileSync(path.join(root, "improv", "teaching.py"), "utf8");
  const scored = [...(/SCORED_KINDS = \[([\s\S]*?)\]/.exec(model)[1]).matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual([...scored].sort(), [...J.SCORING_KINDS].sort());
});

test("the loop is the exercise's bars from bar one, held to the chart", () => {
  assert.deepEqual(P.exerciseRange(exercise, 12), { first: "1", last: "4" });
  assert.deepEqual(P.exerciseRange(exercise, 2), { first: "1", last: "2" });
});

test("a take counts for the exercise only while the chart and the bars are what it asked for", () => {
  const same = { id: 3 };
  assert.equal(P.exerciseApplies(exercise, same, built(0, 4, 12)), true);
  assert.equal(P.exerciseApplies(exercise, same, built(0, 2, 12)), false);
  assert.equal(P.exerciseApplies(exercise, same, built(1, 5, 12)), false);
  assert.equal(P.exerciseApplies(exercise, { id: 4 }, built(0, 4, 12)), false);
  assert.equal(P.exerciseApplies(exercise, same, built(0, 4, 12, { metronome: true })), false);
  assert.equal(P.exerciseApplies(exercise, same, { ok: false }), false);
  assert.equal(P.exerciseApplies(null, same, built(0, 4, 12)), false);
  assert.equal(P.exerciseApplies(exercise, same, built(0, 2, 2)), true);
});

test("the result line says the score and whether it passes, and says nothing before there is a score", () => {
  assert.equal(P.exerciseVerdict(80, 70), "Score 80. That passes (70 needed).");
  assert.equal(P.exerciseVerdict(70, 70), "Score 70. That passes (70 needed).");
  assert.equal(P.exerciseVerdict(40, 70), "Score 40. 70 needed to pass.");
  assert.equal(P.exerciseVerdict(null, 70), "");
  assert.equal(P.exerciseVerdict(0, 70), "Score 0. 70 needed to pass.");
});

test("the real library builds under the exercise's own loop", () => {
  const library = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));
  const progression = library.progressions.find((p) => p.time_signature === "4/4");
  const style = styles.find((s) => s.time_signature === "4/4");
  const whole = P.buildPlan({ progression, style, qualities: theory.chord_qualities, settings: { key: progression.home_key, countIn: 0 } });
  assert.ok(whole.ok, whole.error);
  const range = P.exerciseRange({ bars: 4 }, whole.chart.bars.length);
  const loop = P.buildPlan({ progression, style, qualities: theory.chord_qualities, settings: { key: progression.home_key, countIn: 1, ...range } });
  assert.ok(loop.ok, loop.error);
  assert.equal(loop.to - loop.from, Math.min(4, whole.chart.bars.length));
  assert.equal(P.exerciseApplies({ progression: 9, bars: 4 }, { id: 9 }, loop), true);
});
