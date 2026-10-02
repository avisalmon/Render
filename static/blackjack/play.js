/* The play table: wiring, and nothing about what is right.
   REQ-B.9.1.

   The server owns the shoe, the hole card, the chips and the verdict. This
   file draws the table it is handed and sends the person's choices back, one
   POST each, carrying the `step` it last saw. A stale step comes back as a 409
   with the current table, which is drawn instead, so a double tap or a second
   open tab shows the truth rather than a hand that never happened. */

(function () {
  "use strict";

  var node = document.getElementById("bjTable");
  if (!node) return;

  var BASE = "/blackjack/api/play-tables/";
  var BET_KEY = "bj.sim.bet";
  var WORDS = { H: "קלף", S: "עצירה", D: "הכפלה", P: "פיצול" };
  var RESULTS = { win: "ניצחון", lose: "הפסד", push: "תיקו", blackjack: "בלאקג'ק" };

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    chips: $("bjChips"), shoe: $("bjShoe"), batch: $("bjBatch"),
    dealer: $("bjDealer"), dealerTotal: $("bjDealerTotal"),
    hands: $("bjHands"), hint: $("bjHint"), outcome: $("bjOutcome"),
    error: $("bjError"),
    betPanel: $("bjBetPanel"), bet: $("bjBet"), down: $("bjBetDown"),
    up: $("bjBetUp"), quick: $("bjQuick"), deal: $("bjDeal"),
    insPanel: $("bjInsurancePanel"), insCost: $("bjInsuranceCost"),
    insYes: $("bjInsureYes"), insNo: $("bjInsureNo"),
    actPanel: $("bjActPanel"), actions: $("bjActions"),
    brokePanel: $("bjBrokePanel"), refill: $("bjRefill"),
    verdict: $("bjVerdict"), note: $("bjNote")
  };

  var table = JSON.parse(node.textContent);
  var bet = 0;
  var busy = false;
  var shown = { dealer: 0, hidden: false, hands: [] };
  var seenLog = { round: null, n: 0 };
  var still = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- small helpers ------------------------------------------------------ */

  function make(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function fmt(n) { return Number(n).toLocaleString("en-US"); }

  function readBet() {
    try {
      var v = parseInt(window.localStorage.getItem(BET_KEY), 10);
      return isNaN(v) ? 0 : v;
    } catch (e) { return 0; }
  }

  function keepBet() {
    try { window.localStorage.setItem(BET_KEY, String(bet)); } catch (e) { /* optional */ }
  }

  function maxBet() { return Math.min(table.max_bet, table.chips); }

  function clampBet(v) {
    var step = table.bet_step;
    v = Math.round(v / step) * step;
    return Math.max(table.min_bet, Math.min(maxBet(), v));
  }

  /* --- drawing ------------------------------------------------------------ */

  function cardEl(card, isNew) {
    var cls = "bj-card";
    if (card.down) cls += " is-down";
    if (card.red) cls += " bj-sim-red";
    if (!isNew || still) cls += " is-still";
    var e = make("span", cls);
    if (!card.down) {
      e.textContent = card.r;
      e.appendChild(make("i", null, card.s));
      e.setAttribute("aria-label", card.r + " " + card.s);
    } else {
      e.setAttribute("aria-label", "קלף הפוך");
    }
    return e;
  }

  function totalText(h) {
    return (h.soft && h.total <= 21 ? h.total + " רך" : String(h.total));
  }

  function drawDealer(round) {
    els.dealer.innerHTML = "";
    els.dealerTotal.textContent = "";
    if (!round) { shown.dealer = 0; shown.hidden = false; return; }
    var cards = round.dealer.cards;
    cards.forEach(function (c, i) {
      /* The hole card animates twice: when it is dealt, and when it turns. */
      var flipped = i === 1 && shown.hidden && !c.down;
      els.dealer.appendChild(cardEl(c, i >= shown.dealer || flipped));
    });
    shown.dealer = cards.length;
    shown.hidden = cards.length > 1 && !!cards[1].down;
    els.dealerTotal.textContent = totalText(round.dealer);
  }

  function handResult(h) {
    if (h.state === "bust") return "חרגתם";
    return h.result ? RESULTS[h.result] : "";
  }

  function drawHands(round) {
    els.hands.innerHTML = "";
    if (!round) { shown.hands = []; return; }
    var next = [];
    round.hands.forEach(function (h, i) {
      var wrap = make("div", "bj-sim-hand" + (h.active ? " is-active" : ""));
      var cards = make("div", "bj-hand");
      var before = shown.hands[i] || 0;
      h.cards.forEach(function (c, j) { cards.appendChild(cardEl(c, j >= before)); });
      next.push(h.cards.length);

      var meta = make("p", "bj-sim-hand-meta");
      meta.appendChild(make("span", "bj-total", totalText(h)));
      meta.appendChild(make("span", "bj-muted bj-small",
        "הימור " + fmt(h.bet) + (h.doubled ? " (הוכפל)" : "")));
      if (round.phase === "settled") {
        var label = handResult(h);
        var net = h.net > 0 ? "+" + fmt(h.net) : h.net < 0 ? "−" + fmt(-h.net) : "0";
        var kind = h.net > 0 ? " is-win" : h.net < 0 ? " is-loss" : "";
        meta.appendChild(make("span", "bj-sim-result" + kind, label + " " + net));
      }
      wrap.appendChild(cards);
      wrap.appendChild(meta);
      els.hands.appendChild(wrap);
    });
    shown.hands = next;
  }

  function drawOutcome(round) {
    if (!round || round.phase !== "settled") { els.outcome.hidden = true; return; }
    var n = round.net;
    var text;
    if (round.dealer.natural && round.insurance && n >= 0) {
      text = "הדילר עם בלאקג'ק. הביטוח החזיר את ההימור.";
    } else if (n > 0) {
      text = "זכיתם ב-" + fmt(n) + " ז'יטונים.";
    } else if (n < 0) {
      text = "הפסדתם " + fmt(-n) + " ז'יטונים.";
    } else {
      text = "תיקו. ההימור חזר אליכם.";
    }
    els.outcome.textContent = text;
    els.outcome.className = "bj-sim-outcome" + (n > 0 ? " is-win" : n < 0 ? " is-loss" : "");
    els.outcome.hidden = false;
  }

  function drawBar() {
    els.chips.textContent = fmt(table.chips);
    var s = table.shoe;
    els.shoe.textContent = table.decks + " חפיסות, נשארו " + s.left +
      " קלפים" + (s.shuffles > 1 ? ", ערבוב מס' " + s.shuffles : "");
    var batch = 20;
    var left = batch - table.in_batch;
    els.batch.textContent = left === batch
      ? "הערה אחרי " + batch + " החלטות"
      : "עוד " + left + " " + (left === 1 ? "החלטה" : "החלטות") + " להערה הבאה";
  }

  function drawPanels(round) {
    var inRound = round && round.phase !== "settled";
    var phase = inRound ? round.phase : "bet";

    els.betPanel.hidden = !(phase === "bet" && !table.broke);
    els.brokePanel.hidden = !table.broke;
    els.insPanel.hidden = phase !== "insurance";
    els.actPanel.hidden = phase !== "player";

    if (phase === "bet") {
      bet = clampBet(bet || readBet() || table.min_bet * 2);
      els.bet.textContent = fmt(bet);
      els.down.disabled = busy || bet <= table.min_bet;
      els.up.disabled = busy || bet + table.bet_step > maxBet();
      els.deal.disabled = busy || table.chips < table.min_bet;
      Array.prototype.forEach.call(els.quick.children, function (b) {
        var v = parseInt(b.getAttribute("data-bet"), 10);
        b.disabled = busy || v > maxBet();
        b.classList.toggle("is-on", v === bet);
      });
    }

    if (phase === "insurance") {
      var cost = Math.floor(round.bet / 2);
      els.insCost.textContent = "עולה " + fmt(cost) + " ז'יטונים ומשלם 2 ל-1 אם לדילר יש בלאקג'ק.";
      els.insYes.disabled = busy || table.chips < cost;
      els.insNo.disabled = busy;
    }

    if (phase === "player") {
      var legal = round.legal || [];
      Array.prototype.forEach.call(els.actions.children, function (b) {
        b.disabled = busy || legal.indexOf(b.getAttribute("data-act")) < 0;
      });
      els.hint.textContent = round.hands.length > 1
        ? "(יד " + (activeIndex(round) + 1) + " מתוך " + round.hands.length + ")" : "";
    } else {
      els.hint.textContent = "";
    }
    els.refill.disabled = busy;
  }

  function activeIndex(round) {
    for (var i = 0; i < round.hands.length; i++) if (round.hands[i].active) return i;
    return 0;
  }

  function showNote(text) {
    if (!text) return;
    els.note.innerHTML = "";
    els.note.appendChild(make("p", "bj-batch-note-head", "אחרי 20 החלטות"));
    els.note.appendChild(make("p", "bj-batch-note-text", text));
    els.note.hidden = false;
  }

  function showVerdict(entry) {
    els.verdict.innerHTML = "";
    if (!entry) { els.verdict.hidden = true; return; }
    var head;
    if (entry.kind === "insurance") {
      head = entry.took ? "ביטוח: לא הכי חכם" : "ביטוח: צדקתם שלא";
    } else {
      head = entry.right
        ? "נכון: " + WORDS[entry.chosen]
        : "לא בדיוק. הכי טוב היה: " + WORDS[entry.correct];
    }
    els.verdict.appendChild(make("p", "bj-verdict-head " + (entry.right ? "is-right" : "is-not"), head));
    if (entry.reason) els.verdict.appendChild(make("p", "bj-verdict-why", entry.reason));
    if (entry.fallback_used) {
      els.verdict.appendChild(make("p", "bj-verdict-fallback",
        "ההכפלה לא הייתה אפשרית ביד הזו, אז זו התשובה במקומה."));
    }
    if (entry.kind === "insurance") {
      els.verdict.appendChild(make("p", "bj-verdict-fallback", "ההחלטה הזו לא נספרת בתרגול."));
    }
    els.verdict.hidden = false;
  }

  /* The newest thing the table said about the person's play. Followed by log
     length, so a reload shows the last decision once and a reply that adds
     none leaves what is on screen alone. */
  function followLog(round, firstLoad) {
    if (!round) { seenLog = { round: null, n: 0 }; showVerdict(null); return; }
    var log = round.log || [];
    if (seenLog.round !== round.id) {
      seenLog = { round: round.id, n: 0 };
      if (!firstLoad) { showVerdict(null); }
    }
    if (log.length > seenLog.n || (firstLoad && log.length)) {
      showVerdict(log[log.length - 1]);
    }
    seenLog.n = log.length;
  }

  function showError(text) {
    els.error.textContent = text || "";
    els.error.hidden = !text;
  }

  function render(firstLoad) {
    var round = table.round;
    drawBar();
    drawDealer(round);
    drawHands(round);
    drawOutcome(round);
    followLog(round, firstLoad);
    drawPanels(round);
  }

  /* --- talking to the server --------------------------------------------- */

  function send(path, body) {
    if (busy) return;
    busy = true;
    showError("");
    render(false);

    body.step = table.step;
    fetch(BASE + path + "/", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().then(function (data) { return { status: res.status, data: data }; });
    }).then(function (r) {
      busy = false;
      if (r.status >= 200 && r.status < 300) {
        table = r.data;
        if (r.data.note) showNote(r.data.note);
        if (path === "deal") { els.note.hidden = true; }
        render(false);
      } else {
        if (r.data && r.data.table) table = r.data.table;
        showError((r.data && r.data.detail) || "משהו השתבש. נסו שוב.");
        render(false);
      }
    }).catch(function () {
      busy = false;
      showError("אין חיבור. הטבלה לא השתנתה, אפשר לנסות שוב.");
      render(false);
    });
  }

  els.deal.addEventListener("click", function () {
    keepBet();
    send("deal", { bet: bet });
  });
  els.down.addEventListener("click", function () { bet = clampBet(bet - table.bet_step); render(false); });
  els.up.addEventListener("click", function () { bet = clampBet(bet + table.bet_step); render(false); });
  els.quick.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-bet]");
    if (!b || b.disabled) return;
    bet = clampBet(parseInt(b.getAttribute("data-bet"), 10));
    render(false);
  });
  els.insYes.addEventListener("click", function () { send("insurance", { take: true }); });
  els.insNo.addEventListener("click", function () { send("insurance", { take: false }); });
  els.refill.addEventListener("click", function () { send("refill", {}); });
  els.actions.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-act]");
    if (!b || b.disabled) return;
    send("act", { action: b.getAttribute("data-act") });
  });

  /* The same four letters the buttons carry, for somebody with a keyboard. */
  document.addEventListener("keydown", function (ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey || busy) return;
    var key = ev.key.toUpperCase();
    var b = els.actions.querySelector('[data-act="' + key + '"]');
    if (b && !b.disabled && !els.actPanel.hidden) {
      ev.preventDefault();
      send("act", { action: key });
    }
  });

  bet = readBet();
  render(true);
})();
