/* The drill screen: wiring, not rules.
   REQ-B.4.2, B.4.3.

   Every decision about what is correct lives in drill.js and the chart it was
   given. This file only moves things on and off the page, which is why it has
   no idea what blackjack is. */

(function () {
  "use strict";

  var chartNode = document.getElementById("bjChart");
  if (!chartNode || !window.BJ) return;

  var chart = JSON.parse(chartNode.textContent);
  var elements = {
    player: document.getElementById("bjPlayer"),
    dealer: document.getElementById("bjDealer"),
    total: document.getElementById("bjTotal"),
    ask: document.getElementById("bjAsk"),
    actions: document.getElementById("bjActions"),
    verdict: document.getElementById("bjVerdict"),
    next: document.getElementById("bjNext"),
    score: document.getElementById("bjScore")
  };

  var WORDS = { H: "קלף", S: "עצירה", D: "הכפלה", P: "פיצול" };

  var situation = null;
  var answered = false;
  var askedAt = 0;
  var played = 0;
  var right = 0;

  function showScore() {
    if (!played) {
      elements.score.textContent = "";
      return;
    }
    elements.score.textContent = right + " מתוך " + played;
  }

  function nextHand() {
    situation = window.BJ.nextSituation(chart.cells);
    answered = false;

    window.BJ.deal(situation, elements);
    elements.total.textContent = window.BJ.handTotal(situation.playerCards);
    elements.ask.textContent = "מה עושים?";

    /* The verdict is emptied rather than hidden, so nothing about the correct
       play is in the page between hands (REQ-B.4.2). */
    elements.verdict.innerHTML = "";
    elements.verdict.hidden = true;
    elements.next.hidden = true;

    var legal = window.BJ.legalActions(situation);
    elements.actions.querySelectorAll(".bj-act").forEach(function (button) {
      var allowed = legal.indexOf(button.dataset.act) !== -1;
      button.disabled = !allowed;
      button.classList.remove("is-chosen", "is-answer");
    });

    askedAt = Date.now();
    window.__bjSituation = situation;      /* read by the browser tests */
  }

  function line(className, text) {
    var el = document.createElement("p");
    el.className = className;
    el.textContent = text;
    return el;
  }

  function answer(chosen) {
    if (answered || !situation) return;
    answered = true;

    var verdict = window.BJ.judge(situation, chosen);
    played += 1;
    if (verdict.right) right += 1;

    elements.verdict.innerHTML = "";
    elements.verdict.appendChild(line(
      "bj-verdict-head " + (verdict.right ? "is-right" : "is-not"),
      verdict.right ? "נכון" : "התשובה היא " + WORDS[verdict.correct]
    ));
    elements.verdict.appendChild(line("bj-verdict-why", verdict.reason));

    /* The fallback only earns a line when it differs, and when it does it is
       the thing beginners get wrong: a double you are not allowed to make is a
       hit on a hard hand and a stand on a soft one. */
    if (verdict.fallback && verdict.fallback !== verdict.correct) {
      elements.verdict.appendChild(line(
        "bj-verdict-fallback",
        "אם אי אפשר " + WORDS[verdict.correct] + ": " + WORDS[verdict.fallback]
      ));
    }

    elements.verdict.hidden = false;
    elements.next.hidden = false;
    elements.ask.textContent = "";

    elements.actions.querySelectorAll(".bj-act").forEach(function (button) {
      button.disabled = true;
      if (button.dataset.act === chosen) button.classList.add("is-chosen");
      if (button.dataset.act === verdict.correct) button.classList.add("is-answer");
    });

    /* Recorded after the screen has already updated, so the drill never waits
       on a network. REQ-B.4.4, and the queue in record.js carries it over a
       tunnel. The correct answer is deliberately not sent: the server reads it
       off the chart row, so a client cannot report an accuracy it did not
       earn. */
    if (window.BJRecord) {
      window.BJRecord.record({
        cell_kind: situation.cell.kind,
        cell_player: situation.cell.player,
        cell_dealer: situation.cell.dealer,
        player_cards: situation.playerCards,
        chosen: chosen,
        answer_ms: Math.max(0, Math.min(600000, Date.now() - askedAt)),
        source: "random"
      });
    }

    showScore();
    elements.next.focus();
  }

  elements.actions.addEventListener("click", function (event) {
    var button = event.target.closest(".bj-act");
    if (button && !button.disabled) answer(button.dataset.act);
  });

  elements.next.addEventListener("click", nextHand);

  /* A keyboard is faster than a thumb for anyone drilling at a desk, and the
     letters are already on the buttons. */
  document.addEventListener("keydown", function (event) {
    var key = (event.key || "").toUpperCase();
    if (!answered && WORDS[key]) {
      var button = elements.actions.querySelector('.bj-act[data-act="' + key + '"]');
      if (button && !button.disabled) answer(key);
    } else if (answered && (key === "ENTER" || key === " ")) {
      nextHand();
    }
  });

  window.__bjNextHand = nextHand;          /* read by the browser tests */
  nextHand();
})();
