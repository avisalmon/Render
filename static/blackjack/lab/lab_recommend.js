/* The lab's recommender (REQ-B.11.29): conditions in, a ladder and freeze steps out.

   A small neural network trained offline (blackjack_model/, not part of the
   site) on 12,000 sets of conditions, each paired with the best policy a long
   search found for it on the classic chart. The goal it learned is Avi's: the
   most days that end with a profit, playing the whole day, where a freeze only
   ever sends profit home.

   This file is used by the page and, unchanged, by the offline training code,
   so the network's twelve numbers are turned into a policy in exactly one place. */

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LabRecommend = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MAX_RUNGS = 6, MAX_STEPS = 4;

  function clamp01(v) { return v < 0 ? 0 : v > 1 ? 1 : v; }
  function roundTo(n, unit) { return Math.max(unit, Math.round(n / unit) * unit); }

  /* c: {start, minBet, limit, handsPerDay, decks, h17, das, pays}. Must match
     `features` in blackjack_model/train.py. */
  function features(c) {
    return [
      Math.log(c.start / c.minBet),
      Math.log(c.limit / c.minBet),
      Math.log(c.start),
      Math.log(c.handsPerDay),
      c.decks / 8,
      c.h17 ? 1 : 0,
      c.das ? 1 : 0,
      c.pays === "6:5" ? 1 : 0
    ];
  }

  /* theta, 13 numbers in [0, 1]:
       0  how many rungs (1..6)        1  first bet (1..4 minimum bets)
       2  growth from rung to rung (1x..4x)
       3  how many freeze steps (0..4)
       4+2i  profit that sets step i off (5%..300% of the starting money)
       5+2i  share of the money above the starting amount sent home (5%..100%)
       12 after the last step: stop freezing, or repeat it
     A freeze only ever sends profit home: the table never drops below the
     starting money because of one. */
  function decode(theta, c) {
    var t = theta.map(clamp01);
    var unit = c.minBet;
    var rungs = 1 + Math.min(MAX_RUNGS - 1, Math.floor(t[0] * MAX_RUNGS));
    var first = unit * (1 + Math.min(3, Math.floor(t[1] * 4)));
    var growth = 1 + 3 * t[2];
    var ladder = [], i;
    for (i = 0; i < rungs; i++) {
      var bet = Math.min(c.limit, roundTo(first * Math.pow(growth, i), unit));
      if (ladder.length && bet <= ladder[ladder.length - 1]) break;
      ladder.push(bet);
    }
    var steps = Math.min(MAX_STEPS, Math.floor(t[3] * (MAX_STEPS + 1)));
    var freeze = [];
    var chunk = Math.max(1, Math.round(c.start / 100));
    var base = c.start;
    for (i = 0; i < steps; i++) {
      var gain = roundTo((0.05 + 2.95 * t[4 + 2 * i]) * c.start, chunk);
      var table = base + gain;
      var above = table - c.start;
      var take = Math.min(above, roundTo((0.05 + 0.95 * t[5 + 2 * i]) * above, chunk));
      if (take < 1) break;
      freeze.push([gain, take]);
      base = table - take;
    }
    return {
      start: c.start, minBet: c.minBet, limit: c.limit, ladder: ladder,
      afterWin: "reset", atLimit: "stay", short: "rest", freeze: freeze,
      freezeAfter: t[12] >= 0.5 ? "repeat" : "stop"
    };
  }

  /* The network: dense layers, ReLU between them, the last one clipped to [0, 1]. */
  function predict(model, c) {
    var x = features(c).map(function (v, k) { return (v - model.scaler.mean[k]) / model.scaler.scale[k]; });
    model.layers.forEach(function (layer, n) {
      var last = n === model.layers.length - 1;
      x = layer.W.map(function (row, j) {
        var s = layer.b[j];
        for (var k = 0; k < row.length; k++) s += row[k] * x[k];
        return last ? clamp01(s) : (s > 0 ? s : 0);
      });
    });
    return x;
  }

  /* Conditions the network was trained on. Outside them it still answers, and
     the page says the answer is a guess. */
  function outside(model, c) {
    var why = [];
    var r = model.ranges;
    if (c.start < r.start[0] || c.start > r.start[1]) why.push("start");
    if (c.limit / c.minBet < r.limitRatio[0] || c.limit / c.minBet > r.limitRatio[1]) why.push("limit");
    if (c.handsPerDay < r.handsPerDay[0] || c.handsPerDay > r.handsPerDay[1]) why.push("hands");
    if (r.decks.indexOf(c.decks) < 0) why.push("decks");
    if (c.start < 5 * c.minBet) why.push("start");
    return why;
  }

  function recommend(model, c) {
    return { policy: decode(predict(model, c), c), outside: outside(model, c) };
  }

  return { features: features, decode: decode, predict: predict, outside: outside, recommend: recommend };
});
