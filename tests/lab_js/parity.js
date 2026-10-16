// Replays card orders and decisions recorded from blackjack/engine.py through
// the JavaScript copy and reports every round, so a test can require them to
// match to the chip (REQ-B.11.2). Input on stdin, output on stdout.
const L = require("../../static/blackjack/lab/lab_core.js");
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));

function shoeFor(cards) {
  return {
    cards: cards, position: 0, cutAt: 1e9, shuffles: 0,
    source: function () { throw new Error("the shoe ran out"); }
  };
}

const out = [];
for (const sc of input.scenarios) {
  const shoe = shoeFor(sc.cards);
  const rounds = [];
  if (input.mode === "engine") {
    for (const r of sc.rounds) {
      const st = L.start(shoe, r.bet, sc.rules);
      if (st.phase === "insurance") L.decideInsurance(st, shoe, sc.rules, r.insurance);
      let i = 0;
      while (st.phase === "player") {
        const chips = r.budget - L.staked(st);
        L.act(st, shoe, sc.rules, r.actions[i++], chips);
      }
      rounds.push({
        net: L.net(st), dealer: st.dealer,
        hands: st.hands.map(h => ({ cards: h.cards, bet: h.bet, result: h.result, net: h.net }))
      });
    }
  } else {
    const chart = L.makeChart(input.cells[sc.cellsKey]);
    const counters = { overrideFallbacks: 0 };
    for (const r of sc.rounds) {
      rounds.push({ net: L.playRound(shoe, r.bet, sc.rules, r.budget, chart, sc.overrides, counters) });
    }
    rounds.push({ fallbacks: counters.overrideFallbacks });
  }
  out.push(rounds);
}
process.stdout.write(JSON.stringify(out));
