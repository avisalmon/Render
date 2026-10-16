/* The strategy lab's worker (REQ-B.11.23).

   Plays the hands off the page's own thread, so the screen stays responsive
   and a run can be cancelled. Work is done in short slices with a pause
   between them, because a worker only hears "stop" between slices. Nothing
   leaves this worker but progress and the final result; the hands themselves
   are not kept. */

"use strict";

var core = null;
var stopped = false;
var SLICE_MS = 40;

self.onmessage = function (event) {
  var msg = event.data;
  if (msg.type === "stop") { stopped = true; return; }
  if (msg.type !== "start") return;
  stopped = false;
  try {
    if (!core) { importScripts(msg.core); core = self.LabCore; }
    var cells = msg.cells;
    if (msg.calculate) {
      if (!self.LabBest) importScripts(msg.best);
      cells = self.LabBest.calculate(msg.cfg.rules).cells;
    }
    var chart = core.makeChart(cells);
    if (msg.mode === "days") runDays(msg.cfg, chart);
    else runSearch(msg.cfg, chart);
  } catch (err) {
    self.postMessage({ type: "error", message: String(err && err.message || err) });
  }
};

function runDays(cfg, chart) {
  var run = core.createDays(cfg, chart);
  (function tick() {
    if (stopped) { self.postMessage({ type: "stopped" }); return; }
    try {
      var step = run.step(SLICE_MS);
      self.postMessage({ type: "progress", mode: "days", played: step.played, total: step.days });
      if (step.done) { self.postMessage({ type: "done", mode: "days", result: run.result() }); return; }
    } catch (err) {
      self.postMessage({ type: "error", message: String(err && err.message || err) });
      return;
    }
    setTimeout(tick, 0);
  })();
}

function runSearch(cfg, chart) {
  var run = core.createSearch(cfg, chart);
  (function tick() {
    if (stopped) { run.cancel(); self.postMessage({ type: "stopped" }); return; }
    try {
      var step = run.step(SLICE_MS);
      self.postMessage({
        type: "progress", mode: "search", tries: step.tries, ms: step.ms,
        budgetMs: cfg.budgetMs, best: step.best, baseline: step.baseline
      });
      if (step.done) { self.postMessage({ type: "done", mode: "search", result: run.result() }); return; }
    } catch (err) {
      self.postMessage({ type: "error", message: String(err && err.message || err) });
      return;
    }
    setTimeout(tick, 0);
  })();
}
