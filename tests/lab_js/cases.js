// The policy rules and the runner's promises, one named case at a time.
// `node cases.js --list` names them; `node cases.js <name> <chart.json>` runs one
// and exits non-zero on the first broken promise.
const assert = require("assert");
const L = require("../../static/blackjack/lab/lab_core.js");

function policy(over) { return Object.assign(L.defaultPolicy(), over || {}); }

// Play a scripted run of net results through the policy alone.
function script(pol, results) {
  const ps = L.newPolicyState(pol);
  const bets = [];
  let stopped = false, ended = null;
  for (const r of results) {
    const n = L.nextBet(ps, pol);
    if (n.end) { ended = n.end; break; }
    bets.push(n.bet);
    if (L.settleRound(ps, pol, r)) { stopped = true; break; }
  }
  return { ps, bets, stopped, ended };
}

const cases = {
  ladder_climbs_on_losses_and_resets_on_a_win() {
    const r = script(policy(), [-15, -50, -150, 500, -15]);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 500, 15]);
  },
  a_push_changes_nothing() {
    const r = script(policy(), [-15, 0, 0, -50]);
    assert.deepStrictEqual(r.bets, [15, 50, 50, 50]);
  },
  at_the_table_limit_the_default_keeps_betting_the_top_rung() {
    const r = script(policy({ freeze: [], start: 100000 }), [-15, -50, -150, -300, -300, -300]);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 500, 500, 500]);
  },
  at_the_limit_restart_goes_back_to_the_first_rung() {
    const r = script(policy({ atLimit: "restart", freeze: [] }), [-15, -50, -150, -500, -15]);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 500, 15]);
  },
  at_the_limit_stop_ends_the_day() {
    const r = script(policy({ atLimit: "stop", freeze: [] }), [-15, -50, -150, -500, -15]);
    assert.strictEqual(r.stopped, true);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 500]);
  },
  raising_the_limit_unlocks_the_next_rungs() {
    const ladder = [15, 50, 150, 500, 1000, 2000];
    assert.deepStrictEqual(L.usableLadder(policy({ ladder, limit: 500 })), [15, 50, 150, 500]);
    assert.deepStrictEqual(L.usableLadder(policy({ ladder, limit: 2000 })), ladder);
  },
  after_a_win_stay_keeps_the_rung() {
    const r = script(policy({ afterWin: "stay", freeze: [] }), [-15, -50, 150, 150]);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 150]);
  },
  after_a_win_back_steps_down_one_rung() {
    const r = script(policy({ afterWin: "back", freeze: [] }), [-15, -50, -150, 500, 500, 500]);
    assert.deepStrictEqual(r.bets, [15, 50, 150, 500, 150, 50]);
  },
  when_money_is_short_the_default_bets_what_is_left() {
    const pol = policy({ start: 40, freeze: [] });
    const r = script(pol, [-15, -25]);
    assert.deepStrictEqual(r.bets, [15, 25]);
  },
  when_money_is_short_restart_goes_to_the_first_rung() {
    const pol = policy({ start: 100, short: "restart", freeze: [] });
    const r = script(pol, [-15, -50, -10]);
    assert.deepStrictEqual(r.bets, [15, 50, 15]);
  },
  when_money_is_short_stop_ends_the_day() {
    const pol = policy({ start: 100, short: "stop", freeze: [] });
    const r = script(pol, [-15, -50, -30]);
    assert.strictEqual(r.ended, "stopped");
  },
  below_the_table_minimum_the_day_is_a_bust() {
    const pol = policy({ start: 20, freeze: [] });
    const r = script(pol, [-10, -1]);
    assert.strictEqual(r.ended, "bust");
  },
  freeze_follows_the_default_steps_one_by_one() {
    const pol = policy();
    const ps = L.newPolicyState(pol);
    const win = (n) => L.settleRound(ps, pol, n);
    win(500);  assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 500]);
    win(500);  assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 1000]);
    win(1000); assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 2000]);
    win(2000); assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 4000]);
  },
  freeze_waits_for_the_whole_chunk() {
    const pol = policy();
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 499);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1499, 0]);
    L.settleRound(ps, pol, 1);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 500]);
  },
  freeze_takes_exactly_the_chunk_from_a_big_jump() {
    const pol = policy();
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 700);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1200, 500]);
  },
  after_the_last_step_nothing_more_is_frozen_by_default() {
    const pol = policy({ freeze: [100] });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 100);
    L.settleRound(ps, pol, 5000);
    assert.deepStrictEqual([ps.playing, ps.frozen], [6000, 100]);
  },
  after_the_last_step_the_last_chunk_can_repeat() {
    const pol = policy({ freeze: [100], freezeAfter: "repeat" });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 100);
    L.settleRound(ps, pol, 300);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 400]);
  },
  frozen_money_is_never_bet_again() {
    const pol = policy({ start: 1000 });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 500);
    L.settleRound(ps, pol, -990);
    assert.strictEqual(ps.playing, 10);
    assert.strictEqual(L.nextBet(ps, pol).end, "bust");
    assert.strictEqual(ps.frozen, 500);
  },
  the_freeze_steps_are_a_free_list() {
    const pol = policy({ freeze: [100, 300, 50, 50, 50, 50, 50] });
    const ps = L.newPolicyState(pol);
    for (let i = 0; i < 7; i++) L.settleRound(ps, pol, pol.freeze[i]);
    assert.strictEqual(ps.frozen, 650);
    assert.strictEqual(ps.playing, 1000);
  },

  // ---- the runner ----
  same_seed_same_days(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 3000, days: 12, seed: 99 };
    assert.deepStrictEqual(L.runDays(cfg, chart).summary, L.runDays(cfg, chart).summary);
  },
  a_different_seed_is_a_different_run(chart, rules) {
    const base = { rules, policy: policy(), overrides: {}, handsPerDay: 3000, days: 12 };
    const a = L.runDays(Object.assign({ seed: 1 }, base), chart).summary;
    const b = L.runDays(Object.assign({ seed: 2 }, base), chart).summary;
    assert.notDeepStrictEqual(a.curve.concat(a.avg), b.curve.concat(b.avg));
  },
  with_no_changes_the_twin_is_the_same_run(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 3000, days: 12, seed: 5 };
    const s = L.runDays(cfg, chart).summary;
    assert.strictEqual(s.changed, false);
    assert.strictEqual(s.helped + s.hurt, 0);
    assert.strictEqual(s.ahead, s.classicAhead);
    assert.deepStrictEqual(s.curve, s.classicCurve);
  },
  a_changed_table_plays_the_same_shuffles_but_not_the_same_run(chart, rules) {
    const overrides = {};
    for (let p = 12; p <= 16; p++) for (let d = 2; d <= 11; d++) overrides["hard|" + p + "|" + d] = "S";
    const cfg = { rules, policy: policy(), overrides, handsPerDay: 3000, days: 30, seed: 5 };
    const s = L.runDays(cfg, chart).summary;
    assert.strictEqual(s.changed, true);
    assert.ok(s.helped + s.hurt > 0, "an override that is played should change some day");
  },
  a_day_never_runs_past_its_hand_limit(chart, rules) {
    const pol = policy({ start: 100000, limit: 15, ladder: [15], freeze: [] });
    const cfg = { rules, policy: pol, overrides: {}, handsPerDay: 777, days: 3, seed: 3 };
    const out = L.runDays(cfg, chart);
    assert.strictEqual(out.summary.medianRounds, 777);
  },
  the_summary_is_small_and_the_days_stay_in_the_page(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 100000, days: 200, seed: 1 };
    const out = L.runDays(cfg, chart);
    const size = JSON.stringify(out.summary).length;
    assert.ok(size < 3500, "summary is " + size + " bytes");
    assert.ok(out.summary.curve.length <= 60 && out.summary.classicCurve.length <= 60);
    assert.strictEqual(out.summary.hist.counts.length, 20);
    assert.strictEqual(out.temp.curves.length, 200);
    assert.ok(!("temp" in out.summary) && !("curves" in out.summary));
  },
  an_override_the_table_forbids_falls_back_and_is_counted(chart, rules) {
    const overrides = {};
    for (let d = 2; d <= 11; d++) overrides["hard|16|" + d] = "P";   // a split on a hand that is not a pair
    const cfg = { rules, policy: policy(), overrides, handsPerDay: 3000, days: 40, seed: 8 };
    const s = L.runDays(cfg, chart).summary;
    assert.ok(s.overrideFallbacks > 0, "a split of a hard 16 can never be played, so it must fall back");
  },
  the_search_never_reports_a_worse_policy_on_what_it_trained_on(chart, rules) {
    let t = 0;
    const clock = () => (t += 1);
    const cfg = {
      rules, policy: policy(), overrides: {}, handsPerDay: 500, days: 20, holdoutDays: 40,
      seed: 4, goal: "ahead", maxTries: 30, budgetMs: 1e9
    };
    const r = L.searchPolicies(cfg, chart, clock);
    assert.ok(r.best.train.value >= r.baseline.train.value);
    assert.ok(r.tries <= 30);
    assert.ok("holdout" in r.best && "holdout" in r.baseline);
  },
  the_search_stops_at_its_time_budget(chart, rules) {
    let t = 0;
    const clock = () => (t += 10);
    const cfg = {
      rules, policy: policy(), overrides: {}, handsPerDay: 200, days: 5, holdoutDays: 5,
      seed: 4, goal: "avg", maxTries: 1e9, budgetMs: 500
    };
    const r = L.searchPolicies(cfg, chart, clock);
    assert.ok(r.tries < 100, "tries " + r.tries);
  },
  the_mixed_goal_scores_each_part_as_a_share(chart, rules) {
    const base = {
      rules, policy: policy(), overrides: {}, handsPerDay: 400, days: 20, holdoutDays: 20,
      seed: 6, maxTries: 0, budgetMs: 1e9
    };
    const score = (goal, mix) => L.searchPolicies(Object.assign({ goal, mix }, base), chart).baseline.train;
    const ahead = score("ahead");
    const avg = score("avg");
    const surv = score("survive");
    const onlyAhead = score("mix", { ahead: 1, avg: 0, survive: 0 });
    const onlyAvg = score("mix", { ahead: 0, avg: 1, survive: 0 });
    const onlySurvive = score("mix", { ahead: 0, avg: 0, survive: 1 });
    assert.ok(Math.abs(onlyAhead.value - ahead.ahead) < 1e-9);
    assert.ok(Math.abs(onlyAvg.value - avg.avg / 1000) < 1e-9);
    assert.ok(Math.abs(onlySurvive.value - surv.survive / 400) < 1e-9);
    const half = score("mix", { ahead: 1, avg: 0, survive: 1 });
    assert.ok(Math.abs(half.value - (ahead.ahead + surv.survive / 400) / 2) < 1e-9);
  },
  a_calculated_chart_plays_like_a_given_one(chart, rules) {
    const Best = require("../../static/blackjack/lab/lab_best.js");
    const cells = Best.calculate(rules).cells;
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 2000, days: 10, seed: 2 };
    const a = L.runDays(cfg, L.makeChart(cells)).summary;
    const b = L.runDays(cfg, chart).summary;
    assert.deepStrictEqual(a.curve, b.curve);
  },
  the_summary_says_which_chart_it_was_played_by(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 100, days: 3, seed: 2, chart: "calculated" };
    assert.strictEqual(L.runDays(cfg, chart).summary.chart, "calculated");
    delete cfg.chart;
    assert.strictEqual(L.runDays(cfg, chart).summary.chart, "classic");
  },
  the_search_only_proposes_policies_the_server_will_accept() {
    let p = policy();
    const rng = L.mulberry32(5);
    for (let i = 0; i < 500; i++) {
      p = L.mutate(p, rng);
      assert.ok(p.ladder.length >= 1 && p.ladder.length <= 12);
      assert.ok(p.freeze.length <= 12);
      p.ladder.forEach(v => assert.ok(Number.isInteger(v) && v >= 1 && v <= p.limit));
      p.freeze.forEach(v => assert.ok(Number.isInteger(v) && v >= 1));
    }
  }
};

if (process.argv[2] === "--list") {
  console.log(Object.keys(cases).join("\n"));
} else {
  const fn = cases[process.argv[2]];
  if (!fn) { console.error("no such case"); process.exit(2); }
  let chart = null, rules = null;
  if (process.argv[3]) {
    const d = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
    chart = L.makeChart(d.cells); rules = d.rules;
  }
  fn(chart, rules);
  console.log("ok");
}
