// Checks the calculated chart (lab_best.js) against the published one and
// against the engine. Input on stdin, output on stdout.
//
//   {"task": "compare", "sets": [{"rules": {...}, "cells": [...]}, ...]}
//   {"task": "chart",   "rules": {...}}
//   {"task": "edge",    "rules": {...}, "source": "calculated"|"given", "cells": [...], "rounds": N, "seed": S}
const L = require("../../static/blackjack/lab/lab_core.js");
const B = require("../../static/blackjack/lab/lab_best.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));

function compare(set) {
  const calc = B.calculate(set.rules);
  let same = 0, sameFallback = 0, comparable = 0, worst = 0;
  const differ = [];
  set.cells.forEach((c, i) => {
    const m = calc.cells[i];
    if (m[0] !== c[0] || m[1] !== c[1] || m[2] !== c[2]) throw new Error("the cells are not in the same order");
    if (m[3] === c[3]) {
      same++;
      // A pair's fallback is never played (the engine reads an unsplittable
      // pair as its total), so only the other kinds are compared.
      if (c[0] !== "pair") { comparable++; if (m[4] === c[4]) sameFallback++; }
    } else {
      const ev = calc.ev[c[0] + "|" + c[1] + "|" + c[2]];
      const gap = Math.abs(ev[m[3]] - ev[c[3]]);
      worst = Math.max(worst, gap);
      differ.push({ cell: c.slice(0, 3), classic: c[3], calculated: m[3], gap: gap });
    }
  });
  return { total: set.cells.length, same: same, comparable: comparable, sameFallback: sameFallback, worst: worst, differ: differ };
}

if (input.task === "compare") {
  process.stdout.write(JSON.stringify(input.sets.map(compare)));
} else if (input.task === "chart") {
  const calc = B.calculate(input.rules);
  const plays = {};
  calc.cells.forEach(c => { plays[c[0] + "|" + c[1] + "|" + c[2]] = c[3]; });
  process.stdout.write(JSON.stringify({ plays: plays, count: calc.cells.length }));
} else {
  const cells = input.source === "calculated" ? B.calculate(input.rules).cells : input.cells;
  const chart = L.makeChart(cells);
  const shoe = L.makeShoe(L.seededSource(input.seed, 0, input.rules.decks));
  let net = 0;
  const counters = { overrideFallbacks: 0 };
  for (let i = 0; i < input.rounds; i++) {
    if (L.needsShuffle(shoe)) L.shuffle(shoe);
    net += L.playRound(shoe, 100, input.rules, 1e12, chart, {}, counters);
  }
  process.stdout.write(JSON.stringify({ edge: net / (input.rounds * 100) }));
}
