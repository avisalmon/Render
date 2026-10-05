// improv: the words of the Challenges screen. Pure: no browser, runs under Node.
//
// The server picks each exercise's best take. This file says where the player stands on it in plain
// words, so the Challenges screen and the Progress screen say the same thing.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovBests = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const kindWords = (item) => String(item.scoring_kind || "").replace(/_/g, " ");

  function scoreLine(item) {
    if (!item.attempts) return `Not played yet. Pass mark ${item.pass_score}.`;
    if (item.passed) return `Best ${item.best_score}, past the ${item.pass_score} mark.`;
    return `Best ${item.best_score}. Pass mark ${item.pass_score}.`;
  }

  function attemptsLine(item) {
    if (!item.attempts) return "";
    return item.attempts === 1 ? "1 try" : `${item.attempts} tries`;
  }

  function split(items) {
    return { challenges: items.filter((i) => i.is_challenge), lessons: items.filter((i) => !i.is_challenge) };
  }

  function statusLine(items) {
    const challenges = split(items).challenges;
    if (!challenges.length) return "No challenges yet.";
    const passed = challenges.filter((i) => i.passed).length;
    return `${passed} of ${challenges.length} ${challenges.length === 1 ? "challenge" : "challenges"} passed.`;
  }

  // The best-played exercises first, for the Progress screen: highest best score, then the most
  // tries, then the order the server gave. Exercises never played are left out.
  function top(items, count) {
    return items
      .map((item, index) => ({ item, index }))
      .filter((entry) => entry.item.attempts > 0)
      .sort((a, b) => b.item.best_score - a.item.best_score || b.item.attempts - a.item.attempts || a.index - b.index)
      .slice(0, count)
      .map((entry) => entry.item);
  }

  function playUrl(base, item) {
    return `${base}?exercise=${encodeURIComponent(item.exercise)}`;
  }

  function playLabel(item) {
    return item.attempts ? "Play again" : "Play";
  }

  return { kindWords, scoreLine, attemptsLine, split, statusLine, top, playUrl, playLabel };
});
