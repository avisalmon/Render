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
    // Avi's defaults: start 1,000.
    //  profit 500, take 1,000, keep 500 as the new starting point
    //  profit 500, take 500,   keep 500
    //  profit 1,000, take 500, keep 1,000
    //  profit 2,000, take 1,000, keep 2,000
    const pol = policy();
    const ps = L.newPolicyState(pol);
    const win = (n) => L.settleRound(ps, pol, n);
    win(500);  assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [500, 1000, 500]);
    win(500);  assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [500, 1500, 500]);
    win(1000); assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [1000, 2000, 1000]);
    win(2000); assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [2000, 3000, 2000]);
    win(5000); assert.deepStrictEqual([ps.playing, ps.frozen], [7000, 3000], "no step left");
  },
  freeze_waits_for_the_whole_profit() {
    const pol = policy();
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 499);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1499, 0]);
    L.settleRound(ps, pol, 1);
    assert.deepStrictEqual([ps.playing, ps.frozen], [500, 1000]);
  },
  freeze_takes_one_step_from_a_big_jump() {
    const pol = policy();
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 700);
    assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [700, 1000, 700], "one step, and what is left is the new starting point");
  },
  after_the_last_step_nothing_more_is_frozen_by_default() {
    const pol = policy({ freeze: [100] });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 100);
    L.settleRound(ps, pol, 5000);
    assert.deepStrictEqual([ps.playing, ps.frozen], [6000, 100]);
  },
  after_the_last_step_the_last_step_can_repeat() {
    const pol = policy({ freeze: [100], freezeAfter: "repeat" });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 100);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1000, 100]);
    L.settleRound(ps, pol, 300);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1200, 200], "the profit is counted from the new starting point");
    L.settleRound(ps, pol, 100);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1200, 300]);
  },
  a_step_has_two_numbers_the_profit_that_sets_it_off_and_what_goes_home() {
    // Avi, 2026-10-16: start 1,000; at a profit of 500 send 1,000 home and keep
    // 500 as the new starting point; at a further profit of 500 send 400 home
    // and keep 600 as the next starting point.
    const pol = policy({ start: 1000, freeze: [[500, 1000], [500, 400]] });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 499);
    assert.deepStrictEqual([ps.playing, ps.frozen], [1499, 0], "not yet");
    L.settleRound(ps, pol, 1);
    assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [500, 1000, 500]);
    L.settleRound(ps, pol, 499);
    assert.deepStrictEqual([ps.playing, ps.frozen], [999, 1000], "the second profit counts from 500, not from 1,000");
    L.settleRound(ps, pol, 1);
    assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [600, 1400, 600]);
    L.settleRound(ps, pol, 100000);
    assert.deepStrictEqual([ps.playing, ps.frozen], [100600, 1400], "no step left, nothing more goes home");
  },
  each_step_counts_from_the_starting_point_the_last_one_left() {
    const pol = policy({ start: 1000, freeze: [[500, 1000], [100, 50]] });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 500);
    assert.strictEqual(ps.base, 500);
    L.settleRound(ps, pol, 100);
    assert.deepStrictEqual([ps.playing, ps.frozen, ps.base], [550, 1050, 550]);
  },
  a_bare_number_is_a_step_that_takes_out_what_it_earned() {
    const a = policy({ freeze: [300] });
    const b = policy({ freeze: [[300, 300]] });
    const pa = L.newPolicyState(a), pb = L.newPolicyState(b);
    [250, 100, -40, 400].forEach((n) => { L.settleRound(pa, a, n); L.settleRound(pb, b, n); });
    assert.deepStrictEqual([pa.playing, pa.frozen], [pb.playing, pb.frozen]);
  },
  a_step_cannot_take_more_than_the_table_has() {
    const pol = policy({ start: 1000, freeze: [[10, 5000]] });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 10);
    assert.deepStrictEqual([ps.playing, ps.frozen], [0, 1010]);
    assert.strictEqual(L.nextBet(ps, pol).end, "bust");
  },
  a_freeze_point_in_the_trace_says_what_set_it_off_and_what_was_left(chart, rules) {
    const pol = policy({ start: 200, ladder: [15, 30], limit: 30, freeze: [[20, 60], [20, 10]], freezeAfter: "repeat" });
    const cfg = { rules, policy: pol, overrides: {}, handsPerDay: 500, days: 20, seed: 4 };
    let seen = 0;
    for (let d = 0; d < cfg.days; d++) {
      const { trace } = L.traceDay(cfg, chart, {}, d);
      trace.freezes.forEach((f) => {
        seen++;
        assert.ok(f.reached >= f.base + f.gain);
        assert.strictEqual(f.left, f.reached - f.amount);
        assert.strictEqual(trace.playing[f.round], f.left, "what is left on the table");
      });
    }
    assert.ok(seen > 0);
  },
  frozen_money_is_never_bet_again() {
    const pol = policy({ start: 1000 });
    const ps = L.newPolicyState(pol);
    L.settleRound(ps, pol, 500);
    L.settleRound(ps, pol, -490);
    assert.strictEqual(ps.playing, 10);
    assert.strictEqual(L.nextBet(ps, pol).end, "bust");
    assert.strictEqual(ps.frozen, 1000);
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
  a_day_played_again_from_the_seed_is_the_day_that_was_played(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 3000, days: 25, seed: 31 };
    const run = L.runDays(cfg, chart);
    run.temp.days.forEach((d, i) => {
      const again = L.traceDay(cfg, chart, cfg.overrides, i).result;
      assert.strictEqual(again.total, d.total, "day " + i);
      assert.strictEqual(again.rounds, d.rounds, "day " + i);
      assert.strictEqual(again.ended, d.ended, "day " + i);
      assert.strictEqual(again.frozen, d.frozen, "day " + i);
    });
  },
  the_trace_follows_the_money_hand_by_hand(chart, rules) {
    // A policy that freezes often, so the days have freeze points to check.
    const pol = policy({ start: 200, ladder: [15, 30], limit: 30, freeze: [[25, 25], [25, 25], [25, 40]], freezeAfter: "repeat" });
    const cfg = { rules, policy: pol, overrides: {}, handsPerDay: 500, days: 15, seed: 4 };
    let sawFreeze = false;
    for (let d = 0; d < cfg.days; d++) {
      const { trace, result } = L.traceDay(cfg, chart, {}, d);
      const n = result.rounds;
      assert.strictEqual(trace.playing.length, n + 1);
      assert.strictEqual(trace.frozen.length, n + 1);
      assert.strictEqual(trace.bets.length, n);
      assert.strictEqual(trace.nets.length, n);
      assert.strictEqual(trace.playing[0], pol.start);
      assert.strictEqual(trace.frozen[0], 0);
      for (let i = 1; i <= n; i++) {
        const before = trace.playing[i - 1] + trace.frozen[i - 1];
        const after = trace.playing[i] + trace.frozen[i];
        assert.strictEqual(after - before, trace.nets[i - 1], "day " + d + " hand " + i);
        assert.ok(trace.frozen[i] >= trace.frozen[i - 1], "frozen money only grows");
        assert.ok(trace.bets[i - 1] <= trace.playing[i - 1], "a bet is never more than the playing money");
      }
      let sum = 0, last = 0;
      trace.freezes.forEach((f) => {
        assert.ok(f.round > last, "freeze points are in order");
        last = f.round;
        sum += f.amount;
        assert.strictEqual(trace.frozen[f.round], f.frozen);
        assert.ok(trace.frozen[f.round] > trace.frozen[f.round - 1]);
        sawFreeze = true;
      });
      assert.strictEqual(sum, result.frozen);
      assert.strictEqual(trace.playing[n] + trace.frozen[n], result.total);
    }
    assert.ok(sawFreeze, "no day froze anything, so nothing was checked");
  },
  tracing_a_day_changes_nothing_about_it(chart, rules) {
    const cfg = { rules, policy: policy(), overrides: {}, handsPerDay: 3000, days: 6, seed: 12 };
    const plain = L.playDay(cfg, chart, {}, L.seededSource(cfg.seed, 2, rules.decks), cfg.handsPerDay);
    const traced = L.traceDay(cfg, chart, {}, 2).result;
    assert.strictEqual(plain.total, traced.total);
    assert.strictEqual(plain.rounds, traced.rounds);
  },
  the_day_viewer_keeps_its_window_inside_the_day() {
    const D = require("../../static/blackjack/lab/lab_day.js");
    let w = D.clampWindow(-5, 20, 100);
    assert.deepStrictEqual(w, [0, 25]);
    w = D.clampWindow(90, 130, 100);
    assert.deepStrictEqual(w, [60, 100]);
    w = D.clampWindow(40, 41, 100);
    assert.strictEqual(w[1] - w[0], 10, "never narrower than ten hands");
    w = D.clampWindow(0, 500, 100);
    assert.deepStrictEqual(w, [0, 100]);
    assert.deepStrictEqual(D.clampWindow(0, 3, 4), [0, 4], "a short day is shown whole");
  },
  zooming_keeps_the_hand_under_the_finger_where_it_is() {
    const D = require("../../static/blackjack/lab/lab_day.js");
    const w = D.zoomWindow(0, 100, 1000, 0.5, 25);
    assert.ok(Math.abs((25 - w[0]) / (w[1] - w[0]) - 0.25) < 1e-9);
    assert.ok(Math.abs((w[1] - w[0]) - 50) < 1e-9);
    const out = D.zoomWindow(40, 60, 1000, 4, 50);
    assert.ok(Math.abs((50 - out[0]) / (out[1] - out[0]) - 0.5) < 1e-9);
    assert.deepStrictEqual(D.zoomWindow(0, 100, 100, 2, 50), [0, 100], "cannot zoom out past the whole day");
  },
  panning_stops_at_the_ends_of_the_day() {
    const D = require("../../static/blackjack/lab/lab_day.js");
    assert.deepStrictEqual(D.panWindow(10, 30, 100, -50), [0, 20]);
    assert.deepStrictEqual(D.panWindow(10, 30, 100, 500), [80, 100]);
    assert.deepStrictEqual(D.panWindow(10, 30, 100, 5), [15, 35]);
  },
  the_envelope_is_the_true_min_and_max_of_each_column() {
    const D = require("../../static/blackjack/lab/lab_day.js");
    const rng = L.mulberry32(9);
    const values = [];
    for (let i = 0; i < 5000; i++) values.push(Math.round(rng() * 1000));
    const env = D.envelope(values, 0, 4999, 100);
    for (let c = 0; c < 100; c++) {
      let lo = Infinity, hi = -Infinity;
      for (let i = 0; i < values.length; i++) {
        const col = Math.min(99, Math.max(0, Math.floor(i / 4999 * 100)));
        if (col === c) { lo = Math.min(lo, values[i]); hi = Math.max(hi, values[i]); }
      }
      assert.strictEqual(env.lo[c], lo, "column " + c);
      assert.strictEqual(env.hi[c], hi, "column " + c);
    }
    const all = D.envelope(values, 0, 4999, 1);
    assert.strictEqual(all.lo[0], Math.min.apply(null, values));
    assert.strictEqual(all.hi[0], Math.max.apply(null, values));
  },
  a_long_day_traces_in_a_moment(chart, rules) {
    const pol = policy({ start: 1000000, ladder: [15], limit: 15, freeze: [] });
    const cfg = { rules, policy: pol, overrides: {}, handsPerDay: 100000, days: 1, seed: 1 };
    const t = Date.now();
    const out = L.traceDay(cfg, chart, {}, 0);
    assert.strictEqual(out.result.rounds, 100000);
    assert.strictEqual(out.trace.playing.length, 100001);
    assert.ok(Date.now() - t < 5000, "took " + (Date.now() - t) + " ms");
  },
  the_recommender_in_the_browser_matches_the_trained_network() {
    const R = require("../../static/blackjack/lab/lab_recommend.js");
    const m = require("../../static/blackjack/lab/recommend_model.json");
    assert.ok(m.checks.length >= 20);
    m.checks.forEach((k) => {
      R.features(k.case).forEach((v, i) => assert.ok(Math.abs(v - k.features[i]) < 1e-9, "feature " + i));
      R.predict(m, k.case).forEach((v, i) => assert.ok(Math.abs(v - k.theta[i]) < 1e-5, "output " + i));
    });
  },
  a_recommendation_never_runs_away_and_is_a_valid_policy(chart, rules) {
    const R = require("../../static/blackjack/lab/lab_recommend.js");
    const m = require("../../static/blackjack/lab/recommend_model.json");
    const rng = L.mulberry32(17);
    const pick = (list) => list[Math.floor(rng() * list.length)];
    for (let i = 0; i < 2000; i++) {
      const minBet = pick([1, 5, 10, 15, 25, 50, 100, 7]);
      const c = {
        start: Math.max(minBet, Math.round(10 + rng() * 60000)), minBet, limit: minBet * pick([1, 3, 10, 50, 200, 1000]),
        handsPerDay: pick([1, 50, 100, 400, 800, 5000]), decks: pick([1, 2, 4, 6, 8]),
        h17: rng() < 0.5, das: rng() < 0.5, pays: rng() < 0.5 ? "3:2" : "6:5"
      };
      const { policy } = R.recommend(m, c);
      assert.ok(policy.ladder.length >= 1 && policy.ladder.length <= 12);
      policy.ladder.forEach((b, k) => {
        assert.ok(Number.isInteger(b) && b >= 1 && b <= Math.max(c.limit, c.minBet), "rung " + b);
        if (k) assert.ok(b > policy.ladder[k - 1]);
      });
      assert.ok(policy.freeze.length <= 12);
      let base = c.start;
      policy.freeze.forEach(([gain, take]) => {
        assert.ok(Number.isInteger(gain) && gain >= 1 && Number.isInteger(take) && take >= 1);
        assert.ok(base + gain - take >= c.start, "a freeze took the table below the start");
        base = base + gain - take;
      });
      assert.ok(["reset"].includes(policy.afterWin) && ["stay"].includes(policy.atLimit) && ["rest"].includes(policy.short));
    }
    const advice = R.recommend(m, { start: 1000, minBet: 15, limit: 500, handsPerDay: 400, decks: 6, h17: false, das: true, pays: "3:2" });
    const s = L.runDays({ rules, policy: advice.policy, overrides: {}, handsPerDay: 400, days: 20, seed: 1 }, chart).summary;
    assert.strictEqual(s.days, 20);
    assert.deepStrictEqual(advice.outside, []);
  },
  the_recommender_says_when_it_is_guessing() {
    const R = require("../../static/blackjack/lab/lab_recommend.js");
    const m = require("../../static/blackjack/lab/recommend_model.json");
    const base = { start: 1000, minBet: 15, limit: 500, handsPerDay: 400, decks: 6, h17: false, das: true, pays: "3:2" };
    assert.deepStrictEqual(R.recommend(m, base).outside, []);
    assert.ok(R.recommend(m, Object.assign({}, base, { start: 90000 })).outside.includes("start"));
    assert.ok(R.recommend(m, Object.assign({}, base, { decks: 1 })).outside.includes("decks"));
    assert.ok(R.recommend(m, Object.assign({}, base, { handsPerDay: 5000 })).outside.includes("hands"));
    assert.ok(R.recommend(m, Object.assign({}, base, { limit: 15 })).outside.includes("limit"));
  },
  the_search_only_proposes_policies_the_server_will_accept() {
    let p = policy();
    const rng = L.mulberry32(5);
    for (let i = 0; i < 500; i++) {
      p = L.mutate(p, rng);
      assert.ok(p.ladder.length >= 1 && p.ladder.length <= 12);
      assert.ok(p.freeze.length <= 12);
      p.ladder.forEach(v => assert.ok(Number.isInteger(v) && v >= 1 && v <= p.limit));
      p.freeze.forEach(e => { assert.strictEqual(e.length, 2); e.forEach(v => assert.ok(Number.isInteger(v) && v >= 1)); });
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
