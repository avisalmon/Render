// improv: the progression library's logic, with no page in it. Filtering, sorting, the counts
// behind the filter menus, and the text on a card. The page (library-page.js) reads the
// controls and draws what this returns, so every rule is tested under Node.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./chart.js"));
  else root.ImprovLibrary = factory(root.ImprovChart);
})(typeof self !== "undefined" ? self : this, function (chart) {
  const DIFFICULTY_NAMES = ["Easiest", "Easy", "Medium", "Hard", "Hardest"];
  const PREVIEW_BARS = 8;

  function difficultyName(level) {
    return DIFFICULTY_NAMES[Number(level) - 1] || "";
  }

  // The band plays two to twelve beats a bar, written over four ("4/4", "3/4").
  function beatsOf(signature) {
    const m = /^(\d+)\/4$/.exec(String(signature || ""));
    const n = m ? Number(m[1]) : 0;
    return n >= 2 && n <= 12 ? n : null;
  }

  const blank = (value) => value === undefined || value === null || String(value).trim() === "" || value === "all";

  function haystack(p) {
    return [p.title, p.description, p.genre, ...(p.tags || [])].join(" ").toLowerCase();
  }

  function filterProgressions(list, filters) {
    const f = filters || {};
    const words = blank(f.q) ? [] : String(f.q).toLowerCase().split(/\s+/).filter(Boolean);
    return list.filter((p) => {
      if (!blank(f.genre) && p.genre !== f.genre) return false;
      if (!blank(f.tag) && !(p.tags || []).includes(f.tag)) return false;
      if (!blank(f.difficulty) && p.difficulty !== Number(f.difficulty)) return false;
      if (f.mine && !p.is_mine) return false;
      if (words.length) {
        const text = haystack(p);
        if (!words.every((w) => text.includes(w))) return false;
      }
      return true;
    });
  }

  const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  const titleOf = (p) => String(p.title || "").toLowerCase();

  function sortProgressions(list, by) {
    const out = [...list];
    if (by === "title") return out.sort((a, b) => byText(titleOf(a), titleOf(b)));
    if (by === "genre") {
      return out.sort((a, b) => byText(a.genre, b.genre) || a.difficulty - b.difficulty || byText(titleOf(a), titleOf(b)));
    }
    return out.sort((a, b) => a.difficulty - b.difficulty || byText(titleOf(a), titleOf(b)));
  }

  function tally(values) {
    const counts = new Map();
    for (const v of values) counts.set(v, (counts.get(v) || 0) + 1);
    return [...counts].map(([value, count]) => ({ value, count }));
  }

  // What is in the list, counted, so a menu never offers a choice that finds nothing.
  function facets(list) {
    return {
      genres: tally(list.map((p) => p.genre)).sort((a, b) => byText(a.value, b.value)),
      tags: tally(list.flatMap((p) => p.tags || [])).sort((a, b) => b.count - a.count || byText(a.value, b.value)),
      difficulties: tally(list.map((p) => p.difficulty)).sort((a, b) => a.value - b.value),
    };
  }

  // The words on a card: how many bars the chart plays and its first bars as chord names.
  function describe(progression, qualities) {
    const beatsPerBar = beatsOf(progression.time_signature);
    if (!beatsPerBar) return { ok: false, bars: 0, preview: "", error: `The band cannot play ${progression.time_signature}.` };
    const parsed = chart.parseChart(progression.chart, qualities, { beatsPerBar, homeKey: progression.home_key });
    if (!parsed.ok) return { ok: false, bars: 0, preview: "", error: parsed.error.message };
    const shown = parsed.bars.slice(0, PREVIEW_BARS).map((bar) => bar.chords.map((c) => c.name).join(" "));
    const more = parsed.bars.length > PREVIEW_BARS ? " ..." : "";
    return { ok: true, bars: parsed.bars.length, written: parsed.writtenCount, preview: shown.join(" | ") + more };
  }

  const SORTS = ["difficulty", "title", "genre"];

  // The filters as they sit in the address bar, and back.
  function filtersFromQuery(search) {
    const params = new URLSearchParams(search || "");
    const level = Number(params.get("difficulty"));
    const sort = params.get("sort");
    return {
      genre: params.get("genre") || "",
      tag: params.get("tag") || "",
      difficulty: Number.isInteger(level) && level >= 1 && level <= 5 ? String(level) : "",
      q: params.get("q") || "",
      sort: SORTS.includes(sort) ? sort : "difficulty",
      mine: params.get("mine") === "1",
    };
  }

  function queryFromFilters(filters) {
    const f = filters || {};
    const params = new URLSearchParams();
    for (const key of ["genre", "tag", "difficulty", "q"]) if (!blank(f[key])) params.set(key, String(f[key]).trim());
    if (SORTS.includes(f.sort) && f.sort !== "difficulty") params.set("sort", f.sort);
    if (f.mine) params.set("mine", "1");
    const text = params.toString();
    return text ? "?" + text : "";
  }

  return {
    filterProgressions, sortProgressions, facets, describe, difficultyName, beatsOf,
    filtersFromQuery, queryFromFilters, DIFFICULTY_NAMES, PREVIEW_BARS,
  };
});
