/* The practice table.
   REQ-B.4.1 to B.4.5. No framework, no build step, no sound, ever.

   Everything here runs in the browser against the chart shipped with the page,
   so an answer arrives in the time it takes to look up and the drill keeps
   working with no signal. The server is never asked what the right play was.

   Functions hang off window.BJ so they can be exercised by a real browser in
   the test suite. Dealing logic that is only reachable through a click is
   logic nobody can test, and this is the part that must never be wrong: a
   situation whose cards do not add up to the hand being asked about would
   teach the right answer to the wrong question. */

(function () {
  "use strict";

  var RANKS = { 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9",
                10: "10", 11: "A" };
  var SUITS = ["♠", "♥", "♦", "♣"];

  function pick(list) {
    return list[Math.floor(Math.random() * list.length)];
  }

  /* The cards that make a hand of this shape.

     hard: two cards adding to the total, never a pair (that is a different
           decision) and never containing an ace counted as eleven.
     soft: an ace plus its partner.
     pair: the rank twice; eleven means two aces. */
  function cardsFor(kind, player) {
    if (kind === "pair") {
      return [player, player];
    }
    if (kind === "soft") {
      return [11, player - 11];
    }
    var options = [];
    for (var first = 2; first <= 10; first++) {
      var second = player - first;
      if (second < 2 || second > 10) continue;
      if (first === second) continue;      /* that is a pair, a different cell */
      options.push([first, second]);
    }
    if (!options.length) {
      /* Hard totals of 5 to 11 can need a low card that is not available as a
         pair; fall back to three cards rather than lying about the total. */
      return [10, player - 10 - 2, 2].filter(function (n) { return n >= 2; });
    }
    return pick(options);
  }

  function label(value) {
    return RANKS[value] || String(value);
  }

  function handTotal(cards) {
    var total = 0, aces = 0;
    cards.forEach(function (c) {
      total += c;
      if (c === 11) aces += 1;
    });
    while (total > 21 && aces > 0) { total -= 10; aces -= 1; }
    return total;
  }

  /* Choose what to ask next.

     Mostly random, and sometimes a cell the person has recently missed and not
     since put right. REQ-B.5.7: this is the weak form of spaced repetition and
     it is free on purpose, because a free tier that does not actually teach
     converts nobody, and drilling pure random forever is how people plateau.

     REVIEW_SHARE is a share, not a rule: a drill that only ever asks what you
     are bad at is demoralising and also stops checking what you already knew.
     The real scheduler, reading due dates rather than the last forty hands, is
     the paid feature (REQ-B.8.2). */
  var REVIEW_SHARE = 0.4;

  function nextSituation(cells, review) {
    var cell = null;
    if (review && review.length && Math.random() < REVIEW_SHARE) {
      var want = pick(review);
      cell = cells.filter(function (c) {
        return c.kind === want.kind && c.player === want.player && c.dealer === want.dealer;
      })[0] || null;
    }
    if (!cell) cell = pick(cells);
    return {
      cell: cell,
      playerCards: cardsFor(cell.kind, cell.player),
      dealerCard: cell.dealer
    };
  }

  function cardEl(value, faceDown) {
    var el = document.createElement("span");
    el.className = "bj-card" + (faceDown ? " is-down" : "");
    if (!faceDown) {
      el.textContent = label(value);
      var suit = document.createElement("i");
      suit.textContent = pick(SUITS);
      el.appendChild(suit);
    }
    return el;
  }

  /* Casino order: player, dealer, player, then the dealer's hole card.
     Avi changed his mind about this deliberately and the spec records it, so
     it is written here as the order rather than as a loop nobody can read. */
  var DEAL_ORDER = ["player", "dealer", "player", "hole"];

  function deal(situation, elements, options) {
    var still = (options && options.stillness) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var step = still ? 0 : 160;

    elements.player.innerHTML = "";
    elements.dealer.innerHTML = "";

    var placed = [];
    DEAL_ORDER.forEach(function (who, index) {
      var el, target;
      if (who === "player") {
        var which = placed.filter(function (p) { return p === "player"; }).length;
        el = cardEl(situation.playerCards[which], false);
        target = elements.player;
      } else if (who === "dealer") {
        el = cardEl(situation.dealerCard, false);
        target = elements.dealer;
      } else {
        el = cardEl(null, true);
        target = elements.dealer;
      }
      placed.push(who);
      el.style.animationDelay = (index * step) + "ms";
      if (still) el.classList.add("is-still");
      target.appendChild(el);
    });

    /* A third player card exists only for the hard totals that need one. */
    for (var extra = 2; extra < situation.playerCards.length; extra++) {
      var more = cardEl(situation.playerCards[extra], false);
      more.style.animationDelay = ((DEAL_ORDER.length + extra) * step) + "ms";
      if (still) more.classList.add("is-still");
      elements.player.appendChild(more);
    }
  }

  /* Which actions are even offered for this hand.

     Split is only offered on a pair. Offering it everywhere would be a button
     that is always wrong, which teaches nothing except that one of the four is
     decoration. Double is always offered here because a drilled situation is
     always the first two cards, which is exactly when doubling is allowed. */
  function legalActions(situation) {
    var all = ["H", "S", "D", "P"];
    if (situation.cell.kind !== "pair") {
      all = all.filter(function (a) { return a !== "P"; });
    }
    return all;
  }

  /* The verdict. Deliberately not "wrong": a person drilling three hundred
     hands is told they are wrong often, and the word they read each time
     shapes whether they come back. The correct play and the reason do the
     teaching; the label only says whether to move on or to look again. */
  function judge(situation, chosen) {
    var cell = situation.cell;
    return {
      chosen: chosen,
      correct: cell.action,
      fallback: cell.fallback,
      reason: cell.reason,
      right: chosen === cell.action
    };
  }

  window.BJ = {
    cardsFor: cardsFor,
    handTotal: handTotal,
    nextSituation: nextSituation,
    legalActions: legalActions,
    REVIEW_SHARE: REVIEW_SHARE,
    judge: judge,
    deal: deal,
    label: label,
    DEAL_ORDER: DEAL_ORDER
  };
})();
