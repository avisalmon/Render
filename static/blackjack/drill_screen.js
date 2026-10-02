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
    score: document.getElementById("bjScore"),
    batch: document.getElementById("bjBatch"),
    note: document.getElementById("bjNote")
  };

  var WORDS = { H: "קלף", S: "עצירה", D: "הכפלה", P: "פיצול" };

  var situation = null;
  var answered = false;
  var askedAt = 0;
  var played = 0;
  var right = 0;

  /* Where this person is inside the current twenty. Starts from what the
     server knows, counts locally so it moves the instant a hand is answered,
     and is corrected by the server's reply when that arrives, so a hand
     played in a tunnel still lines up once it is sent. */
  var inBatch = chart.in_batch || 0;
  var BATCH = chart.batch || 20;

  function showScore() {
    if (!played) {
      elements.score.textContent = "";
      return;
    }
    elements.score.textContent = right + " מתוך " + played;
  }

  function showBatch() {
    if (!elements.batch) return;
    var left = BATCH - inBatch;
    elements.batch.textContent = left === BATCH
      ? "הערה אחרי " + BATCH + " ידיים"
      : "עוד " + left + " " + (left === 1 ? "יד" : "ידיים") + " להערה הבאה";
  }

  function showNote(text) {
    if (!elements.note) return;
    elements.note.innerHTML = "";
    elements.note.appendChild(line("bj-batch-note-head", "אחרי " + BATCH + " ידיים"));
    elements.note.appendChild(line("bj-batch-note-text", text));
    elements.note.hidden = false;
  }

  function nextHand() {
    situation = window.BJ.nextSituation(chart.cells, chart.review, chart.due);
    answered = false;

    window.BJ.deal(situation, elements);
    elements.total.textContent = window.BJ.handTotal(situation.playerCards);
    elements.ask.textContent = "מה עושים?";

    /* The verdict is emptied rather than hidden, so nothing about the correct
       play is in the page between hands (REQ-B.4.2). */
    elements.verdict.innerHTML = "";
    elements.verdict.hidden = true;
    elements.next.hidden = true;
    if (elements.note) {
      elements.note.hidden = true;
      elements.note.innerHTML = "";
    }

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

    /* REQ-B.8.3 — the deeper explanation, for whoever is paying. The button
       only appears for them, because an explanation a free user is offered and
       then refused is worse than one never offered: it teaches that the app
       advertises what it will not give. `chart.adaptive` is the same flag that
       decides the schedule, so one answer drives both. */
    if (chart.adaptive) {
      var deeper = document.createElement("button");
      deeper.type = "button";
      deeper.className = "bj-btn bj-btn-small bj-why-more";
      deeper.textContent = "להסביר לעומק";
      deeper.addEventListener("click", function () {
        askDeeper(deeper, situation.cell);
      });
      elements.verdict.appendChild(deeper);
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
        source: situation.source || "random"
      });
    }

    inBatch = (inBatch + 1) % BATCH;
    showScore();
    showBatch();
    elements.next.focus();
  }

  /* The server's word on a recorded hand: the note, if this was the
     twentieth, and the true count into the next twenty. */
  if (window.BJRecord && window.BJRecord.onSent) {
    window.BJRecord.onSent(function (data) {
      if (!data) return;
      if (typeof data.in_batch === "number") {
        inBatch = data.in_batch;
        showBatch();
      }
      if (data.note) showNote(data.note);
    });
  }

  /* The one place in the drill that talks to the server about this hand. It
     is deliberately after the answer and behind a press: the drill itself
     stays instant and offline, and only somebody who asked waits for a
     network. */
  function askDeeper(button, cell) {
    button.disabled = true;
    button.textContent = "רגע…";

    var body = new URLSearchParams({
      kind: cell.kind, player: cell.player, dealer: cell.dealer
    });

    window.fetch("/blackjack/advanced/explain/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "X-CSRFToken": csrf()
      },
      body: body.toString()
    }).then(function (response) {
      return response.json().catch(function () { return {}; });
    }).then(function (data) {
      button.remove();
      elements.verdict.appendChild(
        line("bj-verdict-deeper", data.text || data.refused || "לא הצלחנו להסביר כרגע.")
      );
    }).catch(function () {
      button.disabled = false;
      button.textContent = "להסביר לעומק";
    });
  }

  function csrf() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
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
  showBatch();
  nextHand();
})();
