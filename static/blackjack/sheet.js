/* The cheat sheet's one piece of behaviour: tapping a cell explains it.
   REQ-B.3.4.

   No framework and no build step. The whole app is meant to open instantly on
   a bad connection, and this is thirty lines.

   The reason text comes from the cell's own row in the database, rendered into
   the attribute by the server, so what a person reads here is produced by the
   same logic that produced the answer. */

(function () {
  "use strict";

  var panel = document.getElementById("bjWhy");
  if (!panel) return;

  var WORDS = { H: "קלף", S: "עצירה", D: "הכפלה", P: "פיצול" };

  function explain(button) {
    var action = button.dataset.action;
    var fallback = button.dataset.fallback;

    var head = document.createElement("p");
    head.className = "bj-why-head";
    head.textContent = button.dataset.hand + " מול " + button.dataset.dealer +
      " ← " + (WORDS[action] || action);

    var body = document.createElement("p");
    body.className = "bj-why-body";
    body.textContent = button.dataset.reason;

    panel.innerHTML = "";
    panel.appendChild(head);
    panel.appendChild(body);

    /* The fallback only matters when it differs, and when it does it is the
       thing beginners get wrong: a double you are not allowed to make is a
       hit on hard hands and a stand on soft ones. */
    if (fallback && fallback !== action) {
      var note = document.createElement("p");
      note.className = "bj-why-fallback";
      note.textContent = "אם אי אפשר " + (WORDS[action] || action) +
        ": " + (WORDS[fallback] || fallback);
      panel.appendChild(note);
    }

    document.querySelectorAll(".bj-cell.is-on").forEach(function (el) {
      el.classList.remove("is-on");
    });
    button.classList.add("is-on");
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest(".bj-cell[data-reason]");
    if (button) explain(button);
  });
})();
