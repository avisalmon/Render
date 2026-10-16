/* A saved lab run (REQ-B.11.7): the conditions as words, the summary drawn by
   the same functions as a live result, and a way to delete it. */

(function () {
  "use strict";

  var root = document.getElementById("bjLabRun");
  if (!root) return;

  var boot = JSON.parse(document.getElementById("bjLabRunBoot").textContent);
  var Charts = window.LabCharts;
  var settings = boot.settings, policy = settings.policy;

  function $(id) { return document.getElementById(id); }
  function put(id, text) { $(id).textContent = text; }

  put("runStart", Charts.fmt(policy.start));
  put("runMin", Charts.fmt(policy.minBet));
  put("runLimit", Charts.fmt(policy.limit));
  put("runLadder", policy.ladder.map(Charts.fmt).join(", "));
  put("runFreeze", policy.freeze.length ? policy.freeze.map(Charts.fmt).join(", ") : "בלי הקפאה");
  put("runChart", settings.chart === "calculated" ? "מחושבת" : "קלאסית");
  if (settings.mix) {
    put("runMix", " · שילוב מטרות: ימים ברווח " + settings.mix.ahead + ", ממוצע " + settings.mix.avg + ", משך " + settings.mix.survive);
  }
  put("runHands", Charts.fmt(settings.handsPerDay));
  put("runDays", String(settings.days));
  put("runSeed", String(settings.seed));

  var names = Object.keys(settings.overrides || {});
  if (names.length) put("runOverrides", names.length + " החלטות שונות מהטבלה הקלאסית");
  else $("runOverridesLine").hidden = true;

  if (boot.mode === "days") {
    var s = boot.summary;
    $("runResults").innerHTML = Charts.daysTop(s) + Charts.trendFigure(s) + Charts.histFigure(s);
  } else {
    $("runResults").innerHTML = Charts.searchBody(boot.summary);
  }

  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  $("runDelete").addEventListener("click", function () {
    if (!window.confirm("למחוק את הריצה השמורה?")) return;
    fetch(root.dataset.api, {
      method: "DELETE", credentials: "same-origin",
      headers: { "X-CSRFToken": cookie("csrftoken") }
    }).then(function (r) {
      if (r.status === 204) { window.location.href = root.dataset.list; return; }
      put("runNote", "לא נמחק.");
    }).catch(function () { put("runNote", "לא נמחק, אין חיבור."); });
  });
})();
