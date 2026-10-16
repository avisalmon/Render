/* The strategy lab's engine (SPR-B.12, REQ-B.11.2).

   A JavaScript copy of blackjack/engine.py, and nothing more clever than that:
   the same cards, the same rounds, the same payouts. It exists because the lab
   plays hundreds of thousands of hands and must do it in the person's own
   browser. A test plays the same card orders through both copies and requires
   every round to match to the chip, so a rule changed in one and not the other
   fails the build.

   Runs in a page, in a Web Worker, and under node (the tests). No DOM here.

   Play money only: nothing in this file knows what a chip costs. */

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LabCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var BLACKJACK = 21;
  var PENETRATION = [0.65, 0.78];

  /* ---------- cards ---------- */

  function value(card) {
    var r = card % 13;
    if (r === 0) return 11;
    return r >= 9 ? 10 : r + 1;
  }

  function total(cards) {
    var points = 0, aces = 0, i;
    for (i = 0; i < cards.length; i++) {
      points += value(cards[i]);
      if (cards[i] % 13 === 0) aces++;
    }
    while (points > BLACKJACK && aces) { points -= 10; aces--; }
    return { points: points, soft: aces > 0 };
  }

  function isNatural(cards) {
    return cards.length === 2 && total(cards).points === BLACKJACK;
  }

  /* ---------- randomness: seeded, so a run can be reproduced (REQ-B.11.8) ---------- */

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function mix(a, b, c) {
    var h = (a | 0) ^ Math.imul(((b | 0) + 0x9E3779B9) | 0, 0x85EBCA6B);
    h = Math.imul(h ^ (h >>> 16), 0x7FEB352D);
    h ^= ((c | 0) + 0x165667B1) | 0;
    h = Math.imul(h ^ (h >>> 15), 0x846CA68B);
    return (h ^ (h >>> 16)) >>> 0;
  }

  /* One shuffled shoe, and where its cut card sits. */
  function freshShoe(decks, rng) {
    var cards = [], d, i, j, t;
    for (d = 0; d < decks; d++) for (i = 0; i < 52; i++) cards.push(i);
    for (i = cards.length - 1; i > 0; i--) {
      j = Math.floor(rng() * (i + 1));
      t = cards[i]; cards[i] = cards[j]; cards[j] = t;
    }
    var cutAt = Math.floor(cards.length * (PENETRATION[0] + (PENETRATION[1] - PENETRATION[0]) * rng()));
    return { cards: cards, cutAt: cutAt };
  }

  /* The run and its classic twin ask for the same sequence of shoes by calling
     this with the same seed and day (REQ-B.11.12). */
  function seededSource(seed, day, decks) {
    var k = 0;
    return function () { return freshShoe(decks, mulberry32(mix(seed, day, k++))); };
  }

  function makeShoe(source) {
    var shoe = { cards: [], position: 0, cutAt: 0, source: source, shuffles: 0 };
    shuffle(shoe);
    return shoe;
  }

  function shuffle(shoe) {
    var next = shoe.source();
    shoe.cards = next.cards;
    shoe.cutAt = next.cutAt;
    shoe.position = 0;
    shoe.shuffles++;
  }

  function needsShuffle(shoe) { return shoe.position >= shoe.cutAt; }

  function draw(shoe) {
    if (shoe.position >= shoe.cards.length) shuffle(shoe);
    return shoe.cards[shoe.position++];
  }

  /* ---------- the round, a line-for-line copy of engine.py ---------- */

  function newHand(cards, bet, fromSplit, aces) {
    return {
      cards: cards.slice(), bet: bet, doubled: false,
      from_split: !!fromSplit, aces: !!aces,
      state: "playing", result: null, net: 0
    };
  }

  function start(shoe, bet, rules) {
    var first = draw(shoe), up = draw(shoe), second = draw(shoe), hole = draw(shoe);
    var state = {
      bet: bet, dealer: [up, hole], hands: [newHand([first, second], bet)],
      active: 0, phase: "player", insurance: 0, dealer_natural: false, returned: 0
    };
    if (value(up) === 11) { state.phase = "insurance"; return state; }
    return peek(state, shoe, rules);
  }

  function decideInsurance(state, shoe, rules, take) {
    if (state.phase !== "insurance") throw new Error("no insurance is on offer");
    var cost = take ? Math.floor(state.bet / 2) : 0;
    state.insurance = cost;
    state.phase = "player";
    peek(state, shoe, rules);
    return cost;
  }

  function peek(state, shoe, rules) {
    var up = state.dealer[0], hole = state.dealer[1];
    if ((value(up) === 10 || value(up) === 11) && isNatural([up, hole])) {
      state.dealer_natural = true;
      state.hands.forEach(function (hand) {
        settleProgress(hand, rules);
        if (hand.state === "playing") hand.state = "stand";
      });
      return finish(state, shoe, rules);
    }
    return playOn(state, shoe, rules);
  }

  function canSplitHand(state, hand, rules, chips) {
    if (hand.cards.length !== 2) return false;
    if (value(hand.cards[0]) !== value(hand.cards[1])) return false;
    if (state.hands.length >= rules.max_splits) return false;
    if (hand.aces && !rules.resplit_aces) return false;
    return chips >= hand.bet;
  }

  function legal(state, rules, chips) {
    if (state.phase !== "player") return [];
    var hand = state.hands[state.active];
    if (hand.state !== "playing") return [];
    var locked = hand.aces && !rules.hit_split_aces;
    var actions = locked ? ["S"] : ["H", "S"];
    var two = hand.cards.length === 2;
    if (two && !locked && rules.double_any_two &&
        (!hand.from_split || rules.double_after_split) && chips >= hand.bet) {
      actions.push("D");
    }
    if (canSplitHand(state, hand, rules, chips)) actions.push("P");
    return actions;
  }

  function act(state, shoe, rules, action, chips) {
    if (legal(state, rules, chips).indexOf(action) < 0) {
      throw new Error(action + " is not allowed here");
    }
    var hand = state.hands[state.active];
    var spent = 0;
    if (action === "H") {
      hand.cards.push(draw(shoe));
    } else if (action === "S") {
      hand.state = "stand";
    } else if (action === "D") {
      spent = hand.bet;
      hand.bet += spent;
      hand.doubled = true;
      hand.cards.push(draw(shoe));
      hand.state = "stand";
    } else if (action === "P") {
      spent = hand.bet;
      var aces = value(hand.cards[0]) === 11;
      var kept = hand.cards[0], moved = hand.cards[1];
      hand.cards = [kept, draw(shoe)];
      hand.from_split = true;
      hand.aces = aces;
      var sibling = newHand([moved, draw(shoe)], hand.bet, true, aces);
      state.hands.splice(state.active + 1, 0, sibling);
    }
    playOn(state, shoe, rules);
    return spent;
  }

  function settleProgress(hand, rules) {
    if (hand.state !== "playing") return;
    var points = total(hand.cards).points;
    if (points > BLACKJACK) {
      hand.state = "bust";
    } else if (isNatural(hand.cards) && !hand.from_split) {
      hand.state = "blackjack";
    } else if (points === BLACKJACK) {
      hand.state = "stand";
    } else if (hand.aces && !rules.hit_split_aces &&
               !(rules.resplit_aces && value(hand.cards[0]) === value(hand.cards[1]))) {
      hand.state = "stand";
    }
  }

  function playOn(state, shoe, rules) {
    while (state.active < state.hands.length) {
      var hand = state.hands[state.active];
      settleProgress(hand, rules);
      if (hand.state === "playing") return state;
      state.active++;
    }
    return finish(state, shoe, rules);
  }

  function dealerPlays(state, shoe, rules) {
    var live = state.hands.filter(function (h) { return h.state === "stand"; });
    var cards = state.dealer;
    if (!live.length) return;
    for (;;) {
      var t = total(cards);
      if (t.points < 17 || (t.points === 17 && t.soft && rules.dealer_hits_soft_17)) {
        cards.push(draw(shoe));
      } else {
        return;
      }
    }
  }

  function pays(bet, rules) {
    var parts = String(rules.blackjack_pays).split(":");
    return Math.floor(bet * parseInt(parts[0], 10) / parseInt(parts[1], 10));
  }

  function finish(state, shoe, rules) {
    if (!state.dealer_natural) dealerPlays(state, shoe, rules);
    var dealerPoints = total(state.dealer).points;
    var dealerBust = dealerPoints > BLACKJACK;
    var returned = 0;
    state.hands.forEach(function (hand) {
      var points = total(hand.cards).points;
      if (hand.state === "bust") {
        hand.result = "lose"; hand.net = -hand.bet;
      } else if (hand.state === "blackjack") {
        if (state.dealer_natural) { hand.result = "push"; hand.net = 0; }
        else { hand.result = "blackjack"; hand.net = pays(hand.bet, rules); }
      } else if (state.dealer_natural) {
        hand.result = "lose"; hand.net = -hand.bet;
      } else if (dealerBust || points > dealerPoints) {
        hand.result = "win"; hand.net = hand.bet;
      } else if (points === dealerPoints) {
        hand.result = "push"; hand.net = 0;
      } else {
        hand.result = "lose"; hand.net = -hand.bet;
      }
      returned += hand.bet + hand.net;
    });
    if (state.insurance && state.dealer_natural) returned += state.insurance * 3;
    state.returned = returned;
    state.phase = "settled";
    return state;
  }

  function staked(state) {
    var sum = state.insurance;
    state.hands.forEach(function (h) { sum += h.bet; });
    return sum;
  }

  function net(state) { return state.returned - staked(state); }

  /* The chart cell the active hand is, or null when the chart has no cell. */
  function situation(state, rules, chips) {
    var hand = state.hands[state.active];
    if (canSplitHand(state, hand, rules, chips)) return { kind: "pair", player: value(hand.cards[0]) };
    var t = total(hand.cards);
    if (t.soft && t.points >= 13 && t.points <= 20) return { kind: "soft", player: t.points };
    if (!t.soft && t.points >= 5 && t.points <= 20) return { kind: "hard", player: t.points };
    return null;
  }

  /* ---------- the chart, and a person's changes to it (REQ-B.11.3) ---------- */

  function key(kind, player, dealer) { return kind + "|" + player + "|" + dealer; }

  /* cells: [[kind, player, dealer, action, fallback], ...] from the server. */
  function makeChart(cells) {
    var map = {};
    cells.forEach(function (c) { map[key(c[0], c[1], c[2])] = [c[3], c[4]]; });
    return map;
  }

  /* What the player does with the active hand. `overrides` maps a cell key to
     an action for this run only; an override the table will not allow here
     falls back the way the chart does, and is counted. */
  function chooseAction(state, rules, chips, chart, overrides, counters) {
    var allowed = legal(state, rules, chips);
    var sit = situation(state, rules, chips);
    var hit = allowed.indexOf("H") >= 0 ? "H" : "S";
    if (!sit) return hit;
    var k = key(sit.kind, sit.player, value(state.dealer[0]));
    var cell = chart[k];
    if (!cell) return hit;
    var wanted = cell[0];
    var changed = false;
    if (overrides && overrides[k]) { wanted = overrides[k]; changed = true; }
    if (allowed.indexOf(wanted) >= 0) return wanted;
    if (changed && counters) counters.overrideFallbacks++;
    if (allowed.indexOf(cell[1]) >= 0) return cell[1];
    return hit;
  }

  /* One round for `bet` chips out of `playing`. Insurance is never taken: the
     chart's answer is always no. Returns the net result in chips. */
  function playRound(shoe, bet, rules, playing, chart, overrides, counters) {
    var state = start(shoe, bet, rules);
    if (state.phase === "insurance") decideInsurance(state, shoe, rules, false);
    while (state.phase === "player") {
      var chips = playing - staked(state);
      act(state, shoe, rules, chooseAction(state, rules, chips, chart, overrides, counters), chips);
    }
    return net(state);
  }

  /* ---------- the gambling policy (REQ-B.11.5, B.11.13 to B.11.17) ---------- */

  function defaultPolicy() {
    return {
      start: 1000, minBet: 15, limit: 500,
      ladder: [15, 50, 150, 500],
      afterWin: "reset",      // reset | stay | back
      atLimit: "stay",        // stay | restart | stop
      short: "rest",          // rest | restart | stop
      freeze: [500, 500, 1000, 2000],
      freezeAfter: "stop"     // stop | repeat
    };
  }

  function usableLadder(policy) {
    var rungs = policy.ladder.filter(function (b) { return b >= policy.minBet && b <= policy.limit; });
    return rungs.length ? rungs : [policy.minBet];
  }

  /* The policy as plain state and two small functions, so each rule in the
     spec can be tested with a scripted run of wins and losses and no cards. */

  function newPolicyState(pol) {
    return { ladder: usableLadder(pol), rung: 0, playing: pol.start, frozen: 0, frozenSteps: 0 };
  }

  /* The next bet, or why the day is over (REQ-B.11.13, B.11.15). */
  function nextBet(ps, pol) {
    if (ps.playing < pol.minBet) return { end: "bust" };
    var bet = ps.ladder[ps.rung];
    if (bet > ps.playing) {
      if (pol.short === "stop") return { end: "stopped" };
      if (pol.short === "restart") { ps.rung = 0; bet = ps.ladder[0]; }
      if (bet > ps.playing) bet = ps.playing;
    }
    return { bet: bet };
  }

  /* Book a round's net result: move along the ladder, then freeze winnings
     (REQ-B.11.14, B.11.15, B.11.16). Returns true when the policy says stop. */
  function settleRound(ps, pol, result) {
    var stop = false;
    ps.playing += result;
    if (result > 0) {
      if (pol.afterWin === "reset") ps.rung = 0;
      else if (pol.afterWin === "back") ps.rung = Math.max(0, ps.rung - 1);
    } else if (result < 0) {
      ps.rung++;
      if (ps.rung >= ps.ladder.length) {
        if (pol.atLimit === "restart") ps.rung = 0;
        else {
          ps.rung = ps.ladder.length - 1;
          if (pol.atLimit === "stop") stop = true;
        }
      }
    }
    // Winnings above the starting amount move to the frozen pile, one chunk
    // at a time, and are never bet again.
    for (;;) {
      var chunk;
      if (ps.frozenSteps < pol.freeze.length) chunk = pol.freeze[ps.frozenSteps];
      else if (pol.freezeAfter === "repeat" && pol.freeze.length) chunk = pol.freeze[pol.freeze.length - 1];
      else break;
      if (!(chunk > 0) || ps.playing < pol.start + chunk) break;
      ps.frozen += chunk; ps.playing -= chunk; ps.frozenSteps++;
    }
    return stop;
  }

  /* One day at the casino: up to handsPerDay rounds, ending early on bust or
     when the policy says stop. */
  function playDay(cfg, chart, overrides, source, handsPerDay, curvePoints) {
    var pol = cfg.policy, rules = cfg.rules;
    var shoe = makeShoe(source);
    var ps = newPolicyState(pol);
    var counters = { overrideFallbacks: 0 };
    var step = Math.max(1, Math.ceil(handsPerDay / (curvePoints || 200)));
    var points = Math.floor(handsPerDay / step) + 1;
    var curve = [pol.start];
    var rounds = 0, peak = ps.playing, low = ps.playing, ended = "limit";

    while (rounds < handsPerDay) {
      var next = nextBet(ps, pol);
      if (next.end) { ended = next.end; break; }
      if (needsShuffle(shoe)) shuffle(shoe);
      var result = playRound(shoe, next.bet, rules, ps.playing, chart, overrides, counters);
      rounds++;
      var stopNow = settleRound(ps, pol, result);
      if (ps.playing > peak) peak = ps.playing;
      if (ps.playing < low) low = ps.playing;
      if (rounds % step === 0) curve.push(ps.playing + ps.frozen);
      if (stopNow) { ended = "stopped"; break; }
    }
    var final = ps.playing + ps.frozen;
    if (rounds % step !== 0 && curve.length < points) curve.push(final);
    while (curve.length < points) curve.push(final);
    return {
      total: final, playing: ps.playing, frozen: ps.frozen, rounds: rounds, ended: ended,
      peak: peak, low: low, curve: curve, step: step,
      overrideFallbacks: counters.overrideFallbacks
    };
  }

  /* ---------- many days, each against its classic twin (REQ-B.11.21) ---------- */

  function hasKeys(o) { for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) return true; return false; }

  function median(list) {
    var a = list.slice().sort(function (x, y) { return x - y; });
    if (!a.length) return 0;
    var m = a.length >> 1;
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  }

  function mean(list) {
    if (!list.length) return 0;
    var s = 0; for (var i = 0; i < list.length; i++) s += list[i];
    return s / list.length;
  }

  function downsample(list, n) {
    if (list.length <= n) return list.map(function (v) { return Math.round(v); });
    var out = [];
    for (var i = 0; i < n; i++) out.push(Math.round(list[Math.round(i * (list.length - 1) / (n - 1))]));
    return out;
  }

  function averageCurve(days) {
    var len = days[0].curve.length, out = new Array(len), i, d;
    for (i = 0; i < len; i++) {
      var s = 0;
      for (d = 0; d < days.length; d++) s += days[d].curve[i];
      out[i] = s / days.length;
    }
    return out;
  }

  function histogram(a, b, bins) {
    var lo = Infinity, hi = -Infinity, i;
    a.concat(b).forEach(function (v) { if (v < lo) lo = v; if (v > hi) hi = v; });
    if (hi === lo) hi = lo + 1;
    var width = (hi - lo) / bins;
    function count(list) {
      var c = new Array(bins).fill(0);
      list.forEach(function (v) { c[Math.min(bins - 1, Math.floor((v - lo) / width))]++; });
      return c;
    }
    return { lo: Math.round(lo), hi: Math.round(hi), counts: count(a), classicCounts: count(b) };
  }

  /* cfg: {rules, policy, overrides, handsPerDay, days, seed}.

     A stepper rather than one long call, so a Web Worker can take a "stop"
     message between slices of work. `step(ms)` plays days for about `ms`
     milliseconds and says how far it got. */
  function createDays(cfg, chart, clock) {
    clock = clock || Date.now;
    var overrides = cfg.overrides || {};
    var changed = hasKeys(overrides);
    var mine = [], classic = [], next = 0;
    return {
      step: function (ms) {
        var began = clock();
        while (next < cfg.days && clock() - began < ms) {
          var a = playDay(cfg, chart, overrides, seededSource(cfg.seed, next, cfg.rules.decks), cfg.handsPerDay);
          var b = changed
            ? playDay(cfg, chart, {}, seededSource(cfg.seed, next, cfg.rules.decks), cfg.handsPerDay)
            : a;
          mine.push(a); classic.push(b);
          next++;
        }
        return { done: next >= cfg.days, played: next, days: cfg.days };
      },
      result: function () { return summarise(cfg, mine, classic, changed); }
    };
  }

  function runDays(cfg, chart) {
    var run = createDays(cfg, chart);
    while (!run.step(1000).done) { /* keep going */ }
    return run.result();
  }

  function side(days, start) {
    var totals = days.map(function (x) { return x.total; });
    return {
      ahead: totals.filter(function (t) { return t > start; }).length,
      avg: mean(totals), best: Math.max.apply(null, totals), worst: Math.min.apply(null, totals),
      bust: days.filter(function (x) { return x.ended === "bust"; }).length,
      medianRounds: median(days.map(function (x) { return x.rounds; })),
      frozenAvg: mean(days.map(function (x) { return x.frozen; })),
      totals: totals
    };
  }

  function summarise(cfg, mine, classic, changed) {
    var start = cfg.policy.start;
    var m = side(mine, start), c = changed ? side(classic, start) : m;
    var helped = 0, hurt = 0, i;
    for (i = 0; i < mine.length; i++) {
      if (mine[i].total > classic[i].total) helped++;
      else if (mine[i].total < classic[i].total) hurt++;
    }
    var hist = histogram(m.totals, c.totals, 20);
    var fallbacks = 0;
    mine.forEach(function (x) { fallbacks += x.overrideFallbacks; });
    return {
      summary: {
        days: cfg.days, handsPerDay: cfg.handsPerDay, start: start,
        ahead: m.ahead, classicAhead: c.ahead, helped: helped, hurt: hurt,
        avg: Math.round(m.avg), classicAvg: Math.round(c.avg),
        best: Math.round(m.best), worst: Math.round(m.worst),
        classicBest: Math.round(c.best), classicWorst: Math.round(c.worst),
        bust: m.bust, classicBust: c.bust,
        medianRounds: m.medianRounds, classicMedianRounds: c.medianRounds,
        frozenAvg: Math.round(m.frozenAvg), classicFrozenAvg: Math.round(c.frozenAvg),
        overrideFallbacks: fallbacks, changed: changed, chart: cfg.chart || "classic",
        curve: downsample(averageCurve(mine), 60),
        classicCurve: downsample(averageCurve(classic), 60),
        hist: hist
      },
      // Kept only for the page that is open. Never sent to the server.
      temp: {
        curves: mine.map(function (x) { return downsample(x.curve, 100); }),
        classicCurves: changed ? classic.map(function (x) { return downsample(x.curve, 100); }) : null,
        totals: m.totals, classicTotals: c.totals
      }
    };
  }

  /* ---------- mode two: look for a better policy (REQ-B.11.22) ---------- */

  function score(goal, cfg, chart, policy, days, seed) {
    var one = { rules: cfg.rules, policy: policy };
    var totals = 0, ahead = 0, rounds = 0, d;
    for (d = 0; d < days; d++) {
      var r = playDay(one, chart, cfg.overrides || {}, seededSource(seed, d, cfg.rules.decks), cfg.handsPerDay, 4);
      totals += r.total; rounds += r.rounds;
      if (r.total > policy.start) ahead++;
    }
    var avg = totals / days, surv = rounds / days, frac = ahead / days;
    var value;
    if (goal === "avg") value = avg;
    else if (goal === "survive") value = surv;
    else if (goal === "mix") {
      // Each part on a 0-to-1 footing: a share of the days, the average as a
      // share of the starting money, the hands survived as a share of the day.
      var m = cfg.mix || { ahead: 1, avg: 1, survive: 1 };
      var weights = m.ahead + m.avg + m.survive || 1;
      value = (m.ahead * frac + m.avg * (avg / policy.start) + m.survive * (surv / cfg.handsPerDay)) / weights;
    } else value = frac + avg / 1e9;
    return { value: value, ahead: frac, avg: avg, survive: surv };
  }

  function roundTo(n, unit) { return Math.max(unit, Math.round(n / unit) * unit); }

  function mutate(policy, rng) {
    var p = JSON.parse(JSON.stringify(policy));
    var unit = Math.max(1, p.minBet);
    var chunkUnit = Math.max(1, Math.round(p.start / 20));
    var pick = rng();
    var factor = function () { return Math.pow(2, (rng() - 0.5) * 1.6); };
    if (pick < 0.30 && p.ladder.length) {
      var i = Math.floor(rng() * p.ladder.length);
      p.ladder[i] = Math.min(p.limit, roundTo(p.ladder[i] * factor(), unit));
    } else if (pick < 0.40 && p.ladder.length < 8) {
      p.ladder.push(Math.min(p.limit, roundTo(p.ladder[p.ladder.length - 1] * (1 + rng() * 2), unit)));
    } else if (pick < 0.48 && p.ladder.length > 1) {
      p.ladder.splice(Math.floor(rng() * p.ladder.length), 1);
    } else if (pick < 0.80 && p.freeze.length) {
      var j = Math.floor(rng() * p.freeze.length);
      p.freeze[j] = roundTo(p.freeze[j] * factor(), chunkUnit);
    } else if (pick < 0.90 && p.freeze.length < 6) {
      p.freeze.push(roundTo(p.start * (0.25 + rng() * 1.5), chunkUnit));
    } else if (p.freeze.length) {
      p.freeze.splice(Math.floor(rng() * p.freeze.length), 1);
    }
    p.ladder.sort(function (x, y) { return x - y; });
    return p;
  }

  /* cfg: {rules, policy, overrides, handsPerDay, seed, goal, days, holdoutDays,
     maxTries, budgetMs}. A stepper, for the same reason as `createDays`. */
  function createSearch(cfg, chart, clock) {
    clock = clock || Date.now;
    var began = clock();
    var rng = mulberry32(mix(cfg.seed, 7777, 1));
    var trainSeed = mix(cfg.seed, 101, 0), holdSeed = mix(cfg.seed, 202, 0);
    var baseline = cfg.policy;
    var baseTrain = score(cfg.goal, cfg, chart, baseline, cfg.days, trainSeed);
    var best = baseline, bestTrain = baseTrain, tries = 0, over = false;

    function finished() {
      return over || tries >= cfg.maxTries || clock() - began >= cfg.budgetMs;
    }

    return {
      step: function (ms) {
        var t0 = clock();
        while (!finished() && clock() - t0 < ms) {
          var candidate = mutate(best, rng);
          var s = score(cfg.goal, cfg, chart, candidate, cfg.days, trainSeed);
          tries++;
          if (s.value > bestTrain.value) { best = candidate; bestTrain = s; }
        }
        return { done: finished(), tries: tries, ms: clock() - began, best: bestTrain, baseline: baseTrain };
      },
      cancel: function () { over = true; },
      // The honest part: score both on shuffles the search never saw.
      result: function () {
        var baseHold = score(cfg.goal, cfg, chart, baseline, cfg.holdoutDays, holdSeed);
        var bestHold = best === baseline ? baseHold : score(cfg.goal, cfg, chart, best, cfg.holdoutDays, holdSeed);
        return {
          tries: tries, ms: clock() - began,
          baseline: { policy: baseline, train: baseTrain, holdout: baseHold },
          best: { policy: best, train: bestTrain, holdout: bestHold },
          improved: best !== baseline
        };
      }
    };
  }

  function searchPolicies(cfg, chart, clock) {
    var run = createSearch(cfg, chart, clock);
    while (!run.step(1000).done) { /* keep going */ }
    return run.result();
  }

  return {
    value: value, total: total, isNatural: isNatural,
    mulberry32: mulberry32, mix: mix, freshShoe: freshShoe, seededSource: seededSource,
    makeShoe: makeShoe, needsShuffle: needsShuffle, shuffle: shuffle, draw: draw,
    start: start, decideInsurance: decideInsurance, legal: legal, act: act,
    situation: situation, staked: staked, net: net,
    makeChart: makeChart, chooseAction: chooseAction, playRound: playRound,
    defaultPolicy: defaultPolicy, usableLadder: usableLadder, playDay: playDay,
    newPolicyState: newPolicyState, nextBet: nextBet, settleRound: settleRound,
    createDays: createDays, runDays: runDays, createSearch: createSearch,
    searchPolicies: searchPolicies, mutate: mutate
  };
});
