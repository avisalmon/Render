// improv: the words about the daily workout. Pure: no browser, runs under Node.
//
// The server picks the exercises and says which are done today. This file only says why each was
// picked and where the player stands, in plain words, so the Practice screen and the Today screen
// say the same thing.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovWorkout = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const kindWords = (kind) => String(kind || "").replace(/_/g, " ");

  function xpWords(item) {
    return item.xp_available > 0 ? `Worth ${item.xp_available} XP.` : "No new XP.";
  }

  function reason(item) {
    const lead = {
      next: "Next in your lessons.",
      fresh: "Something to try.",
      review: "A review of one you have passed.",
      weak: `Works on a weak spot: ${kindWords(item.scoring_kind)}.`,
    }[item.slot];
    return lead ? `${lead} ${xpWords(item)}` : xpWords(item);
  }

  function summaryLine(workout) {
    if (!workout.total) return "Nothing to pick yet. Open a lesson and the workout fills up.";
    if (workout.complete) return "Today's workout is done. Well played.";
    return `Today's workout: ${workout.done_today} of ${workout.total} done.`;
  }

  function playUrl(base, item) {
    return `${base}?exercise=${encodeURIComponent(item.exercise)}`;
  }

  function playLabel(item) {
    return item.done_today ? "Play again" : "Play";
  }

  return { reason, summaryLine, playUrl, playLabel };
});
