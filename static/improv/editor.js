// improv: the chart editor's logic, with no page in it. The live check (the first error with
// its line and column), the draft a form edits, and the body the API takes. The page
// (editor-page.js) reads the fields and draws what this returns, so it is tested under Node.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./chart.js"), require("./library.js"));
  else root.ImprovEditor = factory(root.ImprovChart, root.ImprovLibrary);
})(typeof self !== "undefined" ? self : this, function (chart, library) {
  const GENRES = ["jazz", "blues", "pop", "rock", "gospel", "latin", "funk"];
  const HOME_KEYS = [
    "C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B",
    "Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "Bbm", "Bm",
  ];
  const KEY_PATTERN = /^[A-G][#b]?m?$/;
  const COPY_SUFFIX = " (my copy)";
  const TITLE_MAX = 100;
  const CHART_MAX = 20000;

  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  // Where a place in the chart is, as an index into the text a textarea holds.
  function offsetOf(text, line, column) {
    const lines = String(text).split("\n");
    if (line > lines.length) return text.length;
    let offset = 0;
    for (let i = 0; i < Math.max(line, 1) - 1; i++) offset += lines[i].length + 1;
    const own = lines[Math.max(line, 1) - 1] || "";
    return offset + Math.min(Math.max(column - 1, 0), own.length);
  }

  function checkChart(text, qualities, { signature, homeKey } = {}) {
    const beatsPerBar = library.beatsOf(signature);
    if (!beatsPerBar) return { ok: false, message: "The band plays 2/4 to 12/4. Write the time signature like 4/4 or 3/4." };
    const source = String(text || "");
    if (!source.trim()) {
      return { ok: false, empty: true, message: "Write the chart between bar lines, like | Dm7 | G7 | Cmaj7 |" };
    }
    const parsed = chart.parseChart(source, qualities, { beatsPerBar, homeKey });
    if (!parsed.ok) {
      const e = parsed.error;
      const lineText = (source.split("\n")[e.line - 1] || "").replace(/\r$/, "");
      const where = `Line ${e.line}, column ${e.column}` + (e.bar > 0 ? `, bar ${e.bar}` : "");
      return {
        ok: false,
        message: e.message,
        line: e.line,
        column: e.column,
        bar: e.bar,
        lineText,
        caret: " ".repeat(Math.max(e.column - 1, 0)) + "^",
        offset: offsetOf(source, e.line, e.column),
        where,
      };
    }
    const bars = parsed.bars.length;
    const summary = plural(bars, "bar") + (parsed.writtenCount !== bars ? ` (${parsed.writtenCount} written)` : "");
    return { ok: true, bars, written: parsed.writtenCount, summary, parsed };
  }

  // A new or changed progression needs a band; offer one that suits it.
  function suggestStyle(styles, genre, signature) {
    const fits = styles.filter((s) => s.time_signature === signature);
    const match = fits.find((s) => s.genre === genre) || fits[0];
    return match ? match.id : null;
  }

  function blankDraft() {
    return {
      title: "",
      genre: "jazz",
      chart: "| Dm7 | G7 | Cmaj7 | % |",
      home_key: "C",
      time_signature: "4/4",
      default_tempo: 110,
      default_style: null,
      difficulty: 1,
      description: "",
      tags: [],
    };
  }

  // My own row opens to be changed; a preset opens as a copy, which saves as a new row.
  function modeFor(progression) {
    if (!progression) return "new";
    return progression.is_mine ? "edit" : "copy";
  }

  function draftFrom(progression) {
    const edit = modeFor(progression) === "edit";
    const draft = {
      title: progression.title,
      genre: progression.genre,
      chart: progression.chart,
      home_key: progression.home_key,
      time_signature: progression.time_signature,
      default_tempo: progression.default_tempo,
      default_style: progression.default_style === undefined ? null : progression.default_style,
      difficulty: progression.difficulty,
      description: progression.description || "",
      tags: [...(progression.tags || [])],
    };
    if (edit) {
      draft.id = progression.id;
      draft.slug = progression.slug;
    } else {
      draft.title = progression.title.slice(0, TITLE_MAX - COPY_SUFFIX.length) + COPY_SUFFIX;
    }
    return draft;
  }

  // Field by field, what is wrong, in words. Empty means the form can be sent.
  function problems(draft) {
    const found = {};
    const title = String(draft.title || "").trim();
    if (!title) found.title = "Give it a title.";
    else if (title.length > TITLE_MAX) found.title = `A title is at most ${TITLE_MAX} characters.`;
    if (!String(draft.chart || "").trim()) found.chart = "The chart cannot be empty.";
    else if (draft.chart.length > CHART_MAX) found.chart = "The chart is too long.";
    if (!GENRES.includes(draft.genre)) found.genre = "Choose a genre.";
    if (!KEY_PATTERN.test(String(draft.home_key || ""))) found.home_key = "A key like C, Eb or F#m.";
    const tempo = Number(draft.default_tempo);
    if (String(draft.default_tempo).trim() === "" || !Number.isInteger(tempo) || tempo < 20 || tempo > 300) {
      found.default_tempo = "A tempo from 20 to 300 bpm.";
    }
    const level = Number(draft.difficulty);
    if (!Number.isInteger(level) || level < 1 || level > 5) found.difficulty = "A level from 1 to 5.";
    if (!library.beatsOf(draft.time_signature)) found.time_signature = "The band plays 2/4 to 12/4.";
    return found;
  }

  function toBody(draft) {
    const style = draft.default_style;
    return {
      title: String(draft.title || "").trim(),
      genre: draft.genre,
      chart: draft.chart,
      home_key: draft.home_key,
      time_signature: draft.time_signature,
      default_tempo: Number(draft.default_tempo),
      default_style: style === undefined || style === null || style === "" ? null : Number(style),
      difficulty: Number(draft.difficulty),
      description: String(draft.description || "").trim(),
      tags: [...(draft.tags || [])],
    };
  }

  function isDirty(draft, original) {
    const norm = (d) => {
      const body = toBody(d);
      body.tags.sort();
      return JSON.stringify(body);
    };
    return norm(draft) !== norm(original);
  }

  return { checkChart, offsetOf, suggestStyle, blankDraft, modeFor, draftFrom, problems, toBody, isDirty, GENRES, HOME_KEYS };
});
