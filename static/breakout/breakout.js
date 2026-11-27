/* breakout: the library's client-side search and filters (spec 2: a match
   over the rendered cards, no server, no AI), and the shopping list that
   scales with the number of groups (spec 3). */
(function () {
  "use strict";

  // ---- the library ----
  var cards = document.querySelectorAll("#br-cards .br-card");
  var q = document.getElementById("br-q");
  if (cards.length && q) {
    var subject = document.getElementById("br-subject");
    var difficulty = document.getElementById("br-difficulty");
    var grade = document.getElementById("br-grade");
    var hasRuns = document.getElementById("br-has-runs");
    var noMatch = document.getElementById("br-no-match");
    var summary = document.getElementById("br-filter-summary");
    var box = document.getElementById("br-filters");

    function norm(s) { return (s || "").toLowerCase().replace(/["'׳״]/g, ""); }

    function apply() {
      var needle = norm(q.value.trim());
      var subj = subject.value, diff = difficulty.value, g = parseInt(grade.value, 10);
      var onlyRun = hasRuns.checked;
      var shown = 0, active = 0;
      if (needle) active++; if (subj) active++; if (diff) active++; if (grade.value) active++; if (onlyRun) active++;
      cards.forEach(function (card) {
        var ok = true;
        if (needle) ok = (norm(card.dataset.title) + " " + norm(card.dataset.text) + " " + norm(card.dataset.subjects)).indexOf(needle) !== -1;
        if (ok && subj) ok = (" " + card.dataset.subjects + " ").indexOf(" " + subj + " ") !== -1;
        if (ok && diff) ok = card.dataset.difficulty === diff;
        if (ok && !isNaN(g)) ok = parseInt(card.dataset.from, 10) <= g && g <= parseInt(card.dataset.to, 10);
        if (ok && onlyRun) ok = parseInt(card.dataset.runs, 10) > 0;
        card.classList.toggle("br-hidden", !ok);
        if (ok) shown++;
      });
      noMatch.classList.toggle("br-hidden", shown > 0);
      summary.textContent = active ? "(" + active + " פעיל)" : "";
      if (active) box.open = true;  // a filter box with an active filter stays open (methodology 25)
    }

    [q, subject, difficulty, grade, hasRuns].forEach(function (el) {
      el.addEventListener("input", apply);
      el.addEventListener("change", apply);
    });
  }

  // ---- the prep page: one number, "how many groups", scales the shopping
  //      list, the copies on each print and the links' ?groups= ----
  var groups = document.getElementById("br-groups");
  if (groups) {
    var qtys = document.querySelectorAll("#br-shopping .br-qty");
    var copies = document.querySelectorAll(".br-copies");
    var links = document.querySelectorAll("a[data-groups-link]");
    function scale() {
      var n = Math.max(1, Math.min(30, parseInt(groups.value, 10) || 1));
      qtys.forEach(function (el) {
        var per = parseFloat(el.dataset.perGroup) || 0;
        var total = per * n;
        el.textContent = Number.isInteger(total) ? String(total) : total.toFixed(2).replace(/\.?0+$/, "");
      });
      copies.forEach(function (el) { el.textContent = String(n); });
      links.forEach(function (a) { a.href = a.href.replace(/([?&])groups=\d+/, "$1groups=" + n); });
    }
    groups.addEventListener("input", scale);
    groups.addEventListener("change", scale);
  }

  // ---- the editor: a destructive form asks first ----
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      if (!window.confirm(form.dataset.confirm)) ev.preventDefault();
    });
  });
})();
