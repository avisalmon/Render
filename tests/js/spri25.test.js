// SPR-I.2.5 improv: the library (library.js: filter, sort, facets, card text) and the chart
// editor's logic (editor.js: live check with the error where it is, drafts, API bodies).
// The pages are glue and are checked by the pytest wrappers.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const lib = require(path.join(root, "static", "improv", "library.js"));
const editor = require(path.join(root, "static", "improv", "editor.js"));
const theory = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "theory.json"), "utf8"));
const seed = JSON.parse(fs.readFileSync(path.join(root, "improv", "seed_data", "library.json"), "utf8"));

const qualities = theory.chord_qualities.map((q) => ({ symbol: q.symbol, aliases: q.aliases, intervals: q.intervals, roles: q.roles }));
const rows = seed.progressions.map((p, i) => ({ ...p, id: i + 1, is_mine: false, is_preset: true, default_style: null }));
const mine = { ...rows[0], id: 900, slug: "my-own", title: "My own thing", genre: "funk", difficulty: 5, tags: ["funk"], is_mine: true, is_preset: false, description: "Zebra stripes" };
const all = [...rows, mine];
const slugs = (list) => list.map((p) => p.slug);

// ------------------------------------------------------------------- the seed

test("the library holds about forty progressions, every genre, every level and no tag nobody uses", () => {
  assert.ok(seed.progressions.length >= 38 && seed.progressions.length <= 44, `${seed.progressions.length} progressions`);
  const genres = new Set(seed.progressions.map((p) => p.genre));
  for (const g of editor.GENRES) assert.ok(genres.has(g), `no ${g} progression`);
  const levels = new Set(seed.progressions.map((p) => p.difficulty));
  for (const n of [1, 2, 3, 4, 5]) assert.ok(levels.has(n), `nothing at difficulty ${n}`);
  const used = new Set(seed.progressions.flatMap((p) => p.tags));
  for (const t of seed.tags) assert.ok(used.has(t.slug), `the tag ${t.slug} is on no progression`);
  const known = new Set(seed.tags.map((t) => t.slug));
  for (const p of seed.progressions) for (const t of p.tags) assert.ok(known.has(t), `${p.slug} has the unknown tag ${t}`);
});

// ------------------------------------------------------------------- filtering

test("no filter shows everything; a blank, null or 'all' filter is no filter", () => {
  assert.equal(lib.filterProgressions(all, {}).length, all.length);
  assert.equal(lib.filterProgressions(all, { genre: "", tag: null, difficulty: "all", q: "  ", mine: false }).length, all.length);
  assert.equal(lib.filterProgressions(all, undefined).length, all.length);
});

test("genre, tag and difficulty each narrow the list, and together they all have to hold", () => {
  const blues = lib.filterProgressions(all, { genre: "blues" });
  assert.ok(blues.length >= 4 && blues.every((p) => p.genre === "blues"));
  const tagged = lib.filterProgressions(all, { tag: "ii-v-i" });
  assert.ok(tagged.length >= 4 && tagged.every((p) => p.tags.includes("ii-v-i")));
  const level = lib.filterProgressions(all, { difficulty: "5" });
  assert.ok(level.length >= 1 && level.every((p) => p.difficulty === 5));
  assert.deepEqual(slugs(lib.filterProgressions(all, { difficulty: 5 })), slugs(level), "a number and a string are the same level");
  const both = lib.filterProgressions(all, { genre: "jazz", tag: "ii-v-i", difficulty: 1 });
  assert.deepEqual(slugs(both), ["ii-v-i-major", "turnaround-i-vi-ii-v"]);
  assert.deepEqual(lib.filterProgressions(all, { genre: "funk", tag: "blues" }), []);
});

test("search finds words in the title, the description, the genre and the tags, all words at once, any case", () => {
  assert.ok(slugs(lib.filterProgressions(all, { q: "TRITONE" })).includes("tritone-sub-ii-v-i"));
  assert.ok(slugs(lib.filterProgressions(all, { q: "zebra" })).join() === "my-own");
  assert.ok(slugs(lib.filterProgressions(all, { q: "secondary-dominants" })).length >= 3, "tags are searched");
  assert.ok(slugs(lib.filterProgressions(all, { q: "gospel" })).includes("gospel-eight-bars"), "the genre is searched");
  assert.deepEqual(slugs(lib.filterProgressions(all, { q: "zebra stripes" })), ["my-own"]);
  assert.deepEqual(lib.filterProgressions(all, { q: "zebra giraffe" }), []);
});

test("'mine' keeps only my own rows, and works with the other filters", () => {
  assert.deepEqual(slugs(lib.filterProgressions(all, { mine: true })), ["my-own"]);
  assert.deepEqual(lib.filterProgressions(all, { mine: true, genre: "blues" }), []);
});

test("filtering never changes the list it is given", () => {
  const copy = JSON.stringify(all);
  lib.filterProgressions(all, { genre: "blues", q: "x" });
  lib.sortProgressions(all, "title");
  lib.facets(all);
  assert.equal(JSON.stringify(all), copy);
});

// --------------------------------------------------------------------- sorting

test("sort by difficulty (the default), title or genre, each with a stable tie-break", () => {
  const byLevel = lib.sortProgressions(all);
  for (let i = 1; i < byLevel.length; i++) {
    const [a, b] = [byLevel[i - 1], byLevel[i]];
    assert.ok(a.difficulty < b.difficulty || (a.difficulty === b.difficulty && a.title.toLowerCase() <= b.title.toLowerCase()));
  }
  const byTitle = lib.sortProgressions(all, "title");
  const titles = byTitle.map((p) => p.title.toLowerCase());
  assert.deepEqual(titles, [...titles].sort());
  const byGenre = lib.sortProgressions(all, "genre");
  for (let i = 1; i < byGenre.length; i++) assert.ok(byGenre[i - 1].genre <= byGenre[i].genre);
  assert.deepEqual(slugs(lib.sortProgressions(all, "nonsense")), slugs(byLevel), "an unknown sort falls back to difficulty");
});

// ---------------------------------------------------------------------- facets

test("facets count what is in the list, so a menu never offers a choice that finds nothing", () => {
  const f = lib.facets(all);
  assert.equal(f.genres.reduce((n, g) => n + g.count, 0), all.length);
  assert.equal(f.difficulties.reduce((n, d) => n + d.count, 0), all.length);
  assert.deepEqual(f.difficulties.map((d) => d.value), [1, 2, 3, 4, 5]);
  const blues = f.genres.find((g) => g.value === "blues");
  assert.equal(blues.count, lib.filterProgressions(all, { genre: "blues" }).length);
  const tag = f.tags.find((t) => t.value === "ii-v-i");
  assert.equal(tag.count, lib.filterProgressions(all, { tag: "ii-v-i" }).length);
  for (let i = 1; i < f.tags.length; i++) assert.ok(f.tags[i - 1].count >= f.tags[i].count, "tags are listed most used first");
  assert.deepEqual(lib.facets([]), { genres: [], tags: [], difficulties: [] });
});

test("difficulty has a name a person can read", () => {
  assert.deepEqual([1, 2, 3, 4, 5].map(lib.difficultyName), ["Easiest", "Easy", "Medium", "Hard", "Hardest"]);
  assert.equal(lib.difficultyName(9), "");
});

// ------------------------------------------------------------------ card text

test("a card says how many bars the chart plays and shows its first bars as chord names", () => {
  const blues = rows.find((p) => p.slug === "twelve-bar-blues");
  const d = lib.describe(blues, qualities);
  assert.equal(d.ok, true);
  assert.equal(d.bars, 12);
  assert.equal(d.preview, "C7 | F7 | C7 | C7 | F7 | F7 | C7 | C7 ...");
  const short = lib.describe(rows.find((p) => p.slug === "pop-four-chords"), qualities);
  assert.equal(short.preview, "C | G | Am | F", "no dots when the whole chart is shown");
});

test("a card counts the bars as they are played, repeats included, and shows the chord names in full", () => {
  const rhythm = lib.describe(rows.find((p) => p.slug === "rhythm-changes-a"), qualities);
  assert.equal(rhythm.ok, true);
  assert.equal(rhythm.bars, 16);
  const split = lib.describe(rows.find((p) => p.slug === "jazz-blues"), qualities);
  assert.ok(split.preview.includes("Gm7 C7"), split.preview);
});

test("a chart that does not parse gives a card with no preview, not a crash", () => {
  const d = lib.describe({ ...rows[0], chart: "| Dm7 | Zq9 |" }, qualities);
  assert.equal(d.ok, false);
  assert.equal(d.bars, 0);
  assert.equal(d.preview, "");
  assert.ok(d.error.length > 0);
});

test("every seeded progression describes itself", () => {
  for (const p of rows) {
    const d = lib.describe(p, qualities);
    assert.equal(d.ok, true, `${p.slug}: ${d.error}`);
    assert.ok(d.bars >= 4 && d.bars <= 32, `${p.slug} plays ${d.bars} bars`);
  }
});

// ------------------------------------------------------------- the live check

test("a good chart says how many bars it plays", () => {
  const r = editor.checkChart("| Dm7 | G7 | Cmaj7 | % |", qualities, { signature: "4/4", homeKey: "C" });
  assert.equal(r.ok, true);
  assert.equal(r.bars, 4);
  assert.equal(r.summary, "4 bars");
  const one = editor.checkChart("| C |", qualities, { signature: "4/4", homeKey: "C" });
  assert.equal(one.summary, "1 bar");
});

test("repeats are counted as played, and the summary says so", () => {
  const r = editor.checkChart("|: C | F :|", qualities, { signature: "4/4", homeKey: "C" });
  assert.equal(r.bars, 4);
  assert.equal(r.written, 2);
  assert.equal(r.summary, "4 bars (2 written)");
});

test("a bad chord names the line, the column, the bar and the line's own text with a caret under it", () => {
  const text = "| Dm7 | G7 |\n| Cmaj7 | Zq9 |";
  const r = editor.checkChart(text, qualities, { signature: "4/4", homeKey: "C" });
  assert.equal(r.ok, false);
  assert.equal(r.line, 2);
  assert.equal(r.column, 11);
  assert.equal(r.bar, 4);
  assert.equal(r.lineText, "| Cmaj7 | Zq9 |");
  assert.equal(r.caret, " ".repeat(10) + "^");
  assert.equal(r.offset, text.indexOf("Zq9"));
  assert.ok(r.message.toLowerCase().includes("zq9") || r.message.length > 5);
  assert.match(r.where, /^Line 2, column 11/);
});

test("an empty chart is not an error to shout about, but it cannot be saved", () => {
  for (const text of ["", "   \n  "]) {
    const r = editor.checkChart(text, qualities, { signature: "4/4", homeKey: "C" });
    assert.equal(r.ok, false);
    assert.equal(r.empty, true);
    assert.ok(r.message.length > 0);
  }
});

test("a chart with more chords than beats is explained at the bar that has too many", () => {
  const r = editor.checkChart("| C | C F G Am Dm |", qualities, { signature: "4/4", homeKey: "C" });
  assert.equal(r.ok, false);
  assert.equal(r.bar, 2);
  assert.equal(r.line, 1);
});

test("the same chart in three beats a bar has room for three chords, not four", () => {
  assert.equal(editor.checkChart("| C F G |", qualities, { signature: "3/4", homeKey: "C" }).ok, true);
  assert.equal(editor.checkChart("| C F G Am |", qualities, { signature: "3/4", homeKey: "C" }).ok, false);
});

test("a time signature the band cannot play is a clear message, not a parse error", () => {
  for (const signature of ["", "banana", "6/8", "13/4", "1/4"]) {
    const r = editor.checkChart("| C |", qualities, { signature, homeKey: "C" });
    assert.equal(r.ok, false, signature);
    assert.match(r.message, /2\/4 to 12\/4/);
    assert.equal(r.line, undefined);
  }
});

test("offsetOf turns a line and column into a place in the text, and never runs off the end", () => {
  const text = "ab\ncde\nf";
  assert.equal(editor.offsetOf(text, 1, 1), 0);
  assert.equal(editor.offsetOf(text, 2, 2), 4);
  assert.equal(editor.offsetOf(text, 3, 1), 7);
  assert.equal(editor.offsetOf(text, 9, 9), text.length);
  assert.equal(editor.offsetOf(text, 1, 99), 2, "a column past the end of the line stops at the line's end");
  assert.equal(editor.offsetOf("", 1, 1), 0);
});

test("every library chart passes the live check, so the editor never complains about a preset", () => {
  for (const p of rows) {
    const r = editor.checkChart(p.chart, qualities, { signature: p.time_signature, homeKey: p.home_key });
    assert.equal(r.ok, true, `${p.slug}: ${r.message}`);
  }
});

// -------------------------------------------------------------------- drafts

test("a new draft is a playable progression with nothing saved yet", () => {
  const d = editor.blankDraft();
  assert.equal(d.id, undefined);
  assert.deepEqual(Object.keys(editor.problems(d)), ["title"], "only the title is left for the player to write");
  assert.deepEqual(editor.problems({ ...d, title: "Mine" }), {});
  assert.equal(editor.checkChart(d.chart, qualities, { signature: d.time_signature, homeKey: d.home_key }).ok, true);
  assert.deepEqual(d.tags, []);
  assert.equal(editor.modeFor(null), "new");
});

test("my own progression opens to be edited; a preset opens as a copy with its own title", () => {
  assert.equal(editor.modeFor(mine), "edit");
  assert.equal(editor.modeFor(rows[0]), "copy");
  const edit = editor.draftFrom(mine);
  assert.equal(edit.id, 900);
  assert.equal(edit.title, "My own thing");
  const copy = editor.draftFrom(rows[0]);
  assert.equal(copy.id, undefined, "a copy has no id, so saving makes a new row");
  assert.equal(copy.title, "ii-V-I in major (my copy)");
  assert.equal(copy.chart, rows[0].chart);
  assert.notEqual(copy.tags, rows[0].tags, "the tag list is a copy, not shared");
  assert.deepEqual(copy.tags, rows[0].tags);
  const long = editor.draftFrom({ ...rows[0], title: "x".repeat(100) });
  assert.ok(long.title.length <= 100);
  assert.ok(long.title.endsWith("(my copy)"));
});

test("what the player may be told is wrong: title, chart, key, tempo, level, signature, genre", () => {
  const ok = { ...editor.blankDraft(), title: "Fine" };
  const bad = (over) => Object.keys(editor.problems({ ...ok, ...over }));
  assert.deepEqual(bad({ title: "   " }), ["title"]);
  assert.deepEqual(bad({ title: "x".repeat(101) }), ["title"]);
  assert.deepEqual(bad({ chart: " " }), ["chart"]);
  assert.deepEqual(bad({ home_key: "H" }), ["home_key"]);
  assert.deepEqual(bad({ home_key: "C#m" }), []);
  assert.deepEqual(bad({ default_tempo: 19 }), ["default_tempo"]);
  assert.deepEqual(bad({ default_tempo: "301" }), ["default_tempo"]);
  assert.deepEqual(bad({ default_tempo: "" }), ["default_tempo"]);
  assert.deepEqual(bad({ default_tempo: 120.5 }), ["default_tempo"]);
  assert.deepEqual(bad({ default_tempo: "120" }), []);
  assert.deepEqual(bad({ difficulty: 0 }), ["difficulty"]);
  assert.deepEqual(bad({ difficulty: 6 }), ["difficulty"]);
  assert.deepEqual(bad({ time_signature: "7/8" }), ["time_signature"]);
  assert.deepEqual(bad({ genre: "polka" }), ["genre"]);
  assert.ok(Object.values(editor.problems({ ...ok, title: "" })).every((m) => m.length > 0));
});

test("the body sent to the API has the fields it takes, as the types it wants, and nothing it does not", () => {
  const d = {
    ...editor.draftFrom(mine),
    title: "  Trimmed  ",
    default_tempo: "123",
    difficulty: "3",
    default_style: "7",
    description: "  words  ",
  };
  const body = editor.toBody(d);
  assert.equal(body.title, "Trimmed");
  assert.equal(body.default_tempo, 123);
  assert.equal(body.difficulty, 3);
  assert.equal(body.default_style, 7);
  assert.equal(body.description, "words");
  assert.deepEqual(Object.keys(body).sort(), [
    "chart", "default_style", "default_tempo", "description", "difficulty", "genre", "home_key", "tags", "time_signature", "title",
  ]);
  assert.equal(editor.toBody({ ...d, default_style: "" }).default_style, null);
  assert.equal(editor.toBody({ ...d, default_style: null }).default_style, null);
  const t = ["a"];
  assert.notEqual(editor.toBody({ ...d, tags: t }).tags, t, "the tag list is a copy");
});

test("the chart is sent exactly as typed, line breaks and all", () => {
  const chart = "| Dm7 | G7 |\n\n| Cmaj7 | % |\n";
  assert.equal(editor.toBody({ ...editor.blankDraft(), chart }).chart, chart);
});

test("a draft knows whether it has changed since it was loaded", () => {
  const start = editor.draftFrom(mine);
  assert.equal(editor.isDirty(start, editor.draftFrom(mine)), false);
  assert.equal(editor.isDirty({ ...start, title: "Other" }, start), true);
  assert.equal(editor.isDirty({ ...start, tags: ["blues"] }, start), true);
  assert.equal(editor.isDirty({ ...start, tags: ["funk"] }, start), false);
  assert.equal(editor.isDirty({ ...start, default_tempo: "100" }, { ...start, default_tempo: 100 }), false, "100 and '100' are the same tempo");
});

test("the choices a form offers are the ones the server accepts", () => {
  assert.deepEqual(editor.GENRES, ["jazz", "blues", "pop", "rock", "gospel", "latin", "funk"]);
  assert.equal(editor.HOME_KEYS.length, 24);
  for (const k of editor.HOME_KEYS) assert.match(k, /^[A-G][#b]?m?$/);
  assert.ok(editor.HOME_KEYS.includes("C") && editor.HOME_KEYS.includes("Am") && editor.HOME_KEYS.includes("Bb"));
});

// ------------------------------------------------- filters in the address bar

test("filters travel in the address, so Back from Play or the editor returns to the same view", () => {
  const f = lib.filtersFromQuery("?genre=blues&tag=ii-v-i&difficulty=3&q=slow+blues&sort=title&mine=1");
  assert.deepEqual(f, { genre: "blues", tag: "ii-v-i", difficulty: "3", q: "slow blues", sort: "title", mine: true });
  assert.deepEqual(lib.filtersFromQuery(""), { genre: "", tag: "", difficulty: "", q: "", sort: "difficulty", mine: false });
  assert.deepEqual(lib.filtersFromQuery("?sort=junk&mine=0&difficulty=9").sort, "difficulty");
  assert.equal(lib.filtersFromQuery("?mine=0").mine, false);
  assert.equal(lib.queryFromFilters(lib.filtersFromQuery("")), "", "no filters, no query");
  const again = lib.filtersFromQuery(lib.queryFromFilters(f));
  assert.deepEqual(again, f, "what is written can be read back");
  assert.equal(lib.queryFromFilters({ genre: "jazz", sort: "difficulty" }), "?genre=jazz", "the default sort is left out");
  assert.equal(lib.queryFromFilters({ q: "a&b=c" }), "?q=a%26b%3Dc", "text is escaped");
});

// ----------------------------------------------------- the band a form suggests

test("a form suggests the first band of the same genre that fits the bar length, else the first that fits", () => {
  const styles = [
    { id: 1, genre: "pop", time_signature: "4/4" },
    { id: 2, genre: "jazz", time_signature: "3/4" },
    { id: 3, genre: "jazz", time_signature: "4/4" },
    { id: 4, genre: "jazz", time_signature: "4/4" },
  ];
  assert.equal(editor.suggestStyle(styles, "jazz", "4/4"), 3);
  assert.equal(editor.suggestStyle(styles, "jazz", "3/4"), 2);
  assert.equal(editor.suggestStyle(styles, "funk", "4/4"), 1, "no funk band, so the first that fits the bar");
  assert.equal(editor.suggestStyle(styles, "jazz", "5/4"), null, "nothing fits, so no band is chosen");
  assert.equal(editor.suggestStyle([], "jazz", "4/4"), null);
});
