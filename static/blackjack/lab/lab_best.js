/* The strategy lab's calculated chart (REQ-B.11.26).

   Works out the best play for a set of rules, cell by cell, instead of reading
   the published chart. It exists for tables the published chart does not cover
   (one or two decks, say), and as a second opinion on the ones it does.

   **How.** For a cell (a kind of hand against a dealer card) every two-card
   hand that makes it is taken in turn. The dealer's up card and the player's
   two cards are removed from the shoe, and what is left gives the chance of
   each card from then on. The dealer's final total, and the player's value for
   standing, hitting (and then playing on as well as possible), doubling and
   splitting, follow by exact arithmetic over those chances. The cell's value
   for each action is the average over its hands, weighted by how likely each
   is, and the best one wins. Cards drawn after the first two are not removed
   from the chances as they are drawn, which is the one approximation, and it is
   small: the chart is checked against the published one by a test.

   Returns cells in the same shape the server's chart has, so nothing downstream
   knows or cares which it was given. No DOM; runs in a page, a worker or node. */

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LabBest = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var UP = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11];

  function shoeCounts(decks) {
    var c = {}, v;
    for (v = 2; v <= 9; v++) c[v] = 4 * decks;
    c[10] = 16 * decks;
    c[11] = 4 * decks;
    return c;
  }

  /* Add a card to a hand held as (total, soft): an ace is 11 until that would
     bust the hand, and then it is 1. */
  function add(total, soft, v) {
    if (v === 11) {
      if (total + 11 <= 21) return [total + 11, true];
      return [total + 1, soft];
    }
    var t = total + v;
    if (t > 21 && soft) { t -= 10; soft = false; }
    return [t, soft];
  }

  /* Chances for the dealer to finish on 17, 18, 19, 20, 21, or bust. */
  function dealerOutcome(up, p, rules) {
    var memo = {};
    function from(total, soft) {
      if (total > 21) return [0, 0, 0, 0, 0, 1];
      if (total >= 17 && !(total === 17 && soft && rules.dealer_hits_soft_17)) {
        var out = [0, 0, 0, 0, 0, 0];
        out[total - 17] = 1;
        return out;
      }
      var key = total * 2 + (soft ? 1 : 0);
      if (memo[key]) return memo[key];
      var sum = [0, 0, 0, 0, 0, 0], v, i;
      for (v = 2; v <= 11; v++) {
        if (!p[v]) continue;
        var h = add(total, soft, v), r = from(h[0], h[1]);
        for (i = 0; i < 6; i++) sum[i] += p[v] * r[i];
      }
      memo[key] = sum;
      return sum;
    }
    // A dealer who peeks has already looked: the hole card is not the one
    // that makes a natural, and the chances are those of the rest.
    var hole = {}, v, norm = 0;
    for (v = 2; v <= 11; v++) {
      var w = p[v];
      if (rules.dealer_peeks) {
        if (up === 10 && v === 11) w = 0;
        if (up === 11 && v === 10) w = 0;
      }
      hole[v] = w; norm += w;
    }
    var total = [0, 0, 0, 0, 0, 0], start = add(0, false, up);
    for (v = 2; v <= 11; v++) {
      if (!hole[v]) continue;
      var h = add(start[0], start[1], v), r = from(h[0], h[1]);
      for (var i = 0; i < 6; i++) total[i] += hole[v] / norm * r[i];
    }
    return total;
  }

  function standValue(total, dist) {
    if (total > 21) return -1;
    var ev = dist[5], i;
    for (i = 0; i < 5; i++) {
      var f = 17 + i;
      if (f < total) ev += dist[i];
      else if (f > total) ev -= dist[i];
    }
    return ev;
  }

  /* The value of each first decision for one starting hand. `cards` are the two
     values held; `pair` says whether it may be split. */
  function handValues(a, b, up, counts, rules, canSplit) {
    var c = {}, v, n = 0;
    for (v = 2; v <= 11; v++) c[v] = counts[v];
    c[up]--; c[a]--; c[b]--;
    for (v = 2; v <= 11; v++) n += c[v];
    var p = {};
    for (v = 2; v <= 11; v++) p[v] = c[v] / n;
    var dist = dealerOutcome(up, p, rules);

    var memo = {};
    function best(total, soft) {
      if (total > 21) return -1;
      var key = total * 2 + (soft ? 1 : 0);
      if (key in memo) return memo[key];
      var stand = standValue(total, dist), hit = -Infinity;
      if (total < 21) {
        hit = 0;
        for (var v = 2; v <= 11; v++) {
          if (!p[v]) continue;
          var h = add(total, soft, v);
          hit += p[v] * best(h[0], h[1]);
        }
      }
      memo[key] = Math.max(stand, hit);
      return memo[key];
    }
    function hitValue(total, soft) {
      var ev = 0;
      for (var v = 2; v <= 11; v++) {
        if (!p[v]) continue;
        var h = add(total, soft, v);
        ev += p[v] * best(h[0], h[1]);
      }
      return ev;
    }
    function doubleValue(total, soft) {
      var ev = 0;
      for (var v = 2; v <= 11; v++) {
        if (!p[v]) continue;
        var h = add(total, soft, v);
        ev += p[v] * standValue(h[0], dist);
      }
      return 2 * ev;
    }

    var first = add(0, false, a), hand = add(first[0], first[1], b);
    var out = { S: standValue(hand[0], dist), H: hitValue(hand[0], hand[1]), D: doubleValue(hand[0], hand[1]), P: null };

    if (canSplit) {
      var slots = {};
      var slot = function (held) {
        if (held in slots) return slots[held];
        var ev = 0;
        for (var v = 2; v <= 11; v++) {
          if (!p[v]) continue;
          var h = add.apply(null, add(0, false, a).concat([v]));
          var options = [standValue(h[0], dist)];
          var locked = a === 11 && !rules.hit_split_aces;
          if (!locked) {
            if (h[0] < 21) options.push(hitValue(h[0], h[1]));
            if (rules.double_after_split) options.push(doubleValue(h[0], h[1]));
          }
          var canAgain = held < rules.max_splits && v === a && (a !== 11 || rules.resplit_aces);
          if (canAgain) options.push(2 * slot(held + 1));
          ev += p[v] * Math.max.apply(null, options);
        }
        slots[held] = ev;
        return ev;
      };
      out.P = 2 * slot(2);
    }
    return out;
  }

  function combosFor(kind, player, counts, up) {
    var out = [], a, b;
    if (kind === "pair") {
      out.push([player, player, counts[player] * (counts[player] - 1)]);
    } else if (kind === "soft") {
      b = player - 11;
      out.push([11, b, 2 * counts[11] * counts[b]]);
    } else {
      for (a = 2; a <= 10; a++) {
        b = player - a;
        if (b < a || b > 10) continue;
        if (a === b) continue;
        out.push([a, b, 2 * counts[a] * counts[b]]);
      }
      if (!out.length && player % 2 === 0 && player / 2 >= 2 && player / 2 <= 10) {
        out.push([player / 2, player / 2, counts[player / 2] * (counts[player / 2] - 1)]);
      }
    }
    return out;
  }

  function cellValues(kind, player, up, base, rules) {
    var counts = {}, v;
    for (v = 2; v <= 11; v++) counts[v] = base[v];
    counts[up]--;
    var sum = { S: 0, H: 0, D: 0, P: 0 }, weight = 0;
    combosFor(kind, player, counts, up).forEach(function (c) {
      var w = c[2];
      if (w <= 0) return;
      var val = handValues(c[0], c[1], up, base, rules, kind === "pair");
      sum.S += w * val.S; sum.H += w * val.H; sum.D += w * val.D;
      if (val.P != null) sum.P += w * val.P;
      weight += w;
    });
    if (!weight) return null;
    var out = { S: sum.S / weight, H: sum.H / weight, D: sum.D / weight, P: kind === "pair" ? sum.P / weight : null };
    return out;
  }

  var ORDER = ["S", "H", "D", "P"];

  function choose(ev, actions) {
    var best = null;
    actions.forEach(function (a) {
      if (ev[a] == null) return;
      if (best === null || ev[a] > ev[best] + 1e-12) best = a;
    });
    return best;
  }

  /* The chart for `rules`: [[kind, player, dealer, action, fallback], ...] in
     the order the server's chart is in, and `ev` with each cell's values. */
  function calculate(rules) {
    var base = shoeCounts(rules.decks);
    var cells = [], ev = {};
    function cell(kind, player, up) {
      var values = cellValues(kind, player, up, base, rules);
      var action = choose(values, ORDER);
      var fallback = action;
      if (action === "D") fallback = choose(values, ["S", "H"]);
      else if (action === "P") fallback = choose(values, ["S", "H", "D"]);
      ev[kind + "|" + player + "|" + up] = values;
      cells.push([kind, player, up, action, fallback]);
    }
    var t, u, r;
    for (t = 5; t <= 20; t++) for (u = 0; u < UP.length; u++) cell("hard", t, UP[u]);
    for (t = 13; t <= 20; t++) for (u = 0; u < UP.length; u++) cell("soft", t, UP[u]);
    for (r = 2; r <= 11; r++) for (u = 0; u < UP.length; u++) cell("pair", r, UP[u]);
    return { cells: cells, ev: ev };
  }

  return { calculate: calculate, shoeCounts: shoeCounts };
});
