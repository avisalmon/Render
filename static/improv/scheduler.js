// improv: the look-ahead scheduler. Pure: the clock, the timer and the sound are handed
// in, so it runs under Node with a fake clock in the tests and on the page with the
// AudioContext's clock.
//
// A timer that fires every few tens of milliseconds is never trusted with the beat. It
// only asks "which bars start in the next fraction of a second?" and queues their events
// on the audio clock, ahead of time. The audio clock keeps the time; the timer can be
// late by a lot and the band stays on the grid.
//
//   const s = ImprovScheduler.createScheduler({ now, onEvent, setTimer, clearTimer });
//   s.start(plan, { bpm: 120, loop: true });     // plan from ImprovBand.planBand
//   (loopFrom: the bar a loop returns to, so a count-in is played once)
//   s.setBpm(132);                               // from the next bar line
//   s.setPlan(newPlan);                          // a plan of the same shape, from the next bar line
//   s.nextBarAt                                  // when that next bar line is, on the audio clock
//   s.barAt(now())                               // { index, beat, pass } for the screen
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovScheduler = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const MIN_BPM = 20;
  const MAX_BPM = 300;
  const LOOKAHEAD = 0.15;
  const INTERVAL_MS = 30;
  const LATE_LIMIT = 0.25;
  const START_DELAY = 0.06;

  function createScheduler(deps) {
    const lookahead = deps.lookahead === undefined ? LOOKAHEAD : deps.lookahead;
    const intervalMs = deps.intervalMs === undefined ? INTERVAL_MS : deps.intervalMs;
    let plan = null;
    let loop = true;
    let loopFrom = 0; // the bar a looping plan returns to (past a count-in)
    let bpm = 120;
    let cursor = null; // the next bar to queue: { index, pass, start }
    let queued = []; // bars already queued: { index, pass, start, end, secondsPerBeat }
    let timer = null;
    let running = false;
    let lateBars = 0;
    let finishAt = 0; // when the last bar of a non-looping plan ends

    function clampBpm(value) {
      return Math.min(MAX_BPM, Math.max(MIN_BPM, Number(value)));
    }

    function queueBar() {
      const bar = plan.bars[cursor.index];
      const secondsPerBeat = 60 / bpm;
      const end = cursor.start + bar.beats * secondsPerBeat;
      for (const event of bar.events) {
        deps.onEvent(event, cursor.start + event.beat * secondsPerBeat, event.beats * secondsPerBeat);
      }
      queued.push({ index: cursor.index, pass: cursor.pass, start: cursor.start, end, secondsPerBeat });
      if (deps.onBar) deps.onBar(cursor.index, cursor.start, cursor.pass);
      let nextIndex = cursor.index + 1;
      let nextPass = cursor.pass;
      if (nextIndex >= plan.bars.length) {
        if (!loop) return end;
        nextIndex = loopFrom;
        nextPass += 1;
      }
      cursor = { index: nextIndex, pass: nextPass, start: end };
      return null;
    }

    function tick() {
      timer = null;
      if (!running) return;
      const now = deps.now();
      while (cursor && cursor.start < now + lookahead) {
        // The page was busy or hidden and the bar's start is already behind us: start it
        // now rather than fire a burst of notes in the past.
        if (cursor.start < now - LATE_LIMIT) {
          cursor = { ...cursor, start: now + START_DELAY };
          lateBars += 1;
        }
        const ended = queueBar();
        if (ended !== null) {
          finishAt = ended;
          cursor = null;
        }
      }
      queued = queued.filter((b) => b.end > now - 2);
      if (cursor === null && now >= finishAt) {
        running = false;
        if (deps.onEnd) deps.onEnd();
        return;
      }
      timer = deps.setTimer(tick, intervalMs);
    }

    return {
      start(newPlan, options) {
        this.stop();
        const opts = options || {};
        plan = newPlan;
        loop = opts.loop !== false;
        loopFrom = Math.min(Math.max(0, opts.loopFrom || 0), newPlan.bars.length - 1);
        bpm = clampBpm(opts.bpm === undefined ? 120 : opts.bpm);
        const at = opts.at === undefined ? deps.now() + START_DELAY : opts.at;
        cursor = { index: opts.fromBar || 0, pass: 0, start: at };
        queued = [];
        lateBars = 0;
        finishAt = 0;
        running = true;
        tick();
      },

      stop() {
        running = false;
        cursor = null;
        if (timer !== null) deps.clearTimer(timer);
        timer = null;
      },

      // Takes effect on the first bar that has not been queued yet, never mid-bar.
      setBpm(value) {
        bpm = clampBpm(value);
      },

      // Swaps the plan from the first bar that has not been queued yet, for a key, swing or band
      // change while it plays. The new plan must have the same bars and bar length, so the place
      // in the loop is still the place. Gives back when the change is heard, or null if it was
      // refused (nothing is playing, or the shape differs) and the old plan plays on.
      setPlan(newPlan) {
        if (!running || !plan || cursor === null) return null;
        if (!newPlan || !newPlan.bars || newPlan.bars.length !== plan.bars.length) return null;
        if (newPlan.beatsPerBar !== plan.beatsPerBar) return null;
        plan = newPlan;
        return cursor.start;
      },

      // The start of the first bar not yet queued: where a change made now will be heard.
      get nextBarAt() {
        return running && cursor !== null ? cursor.start : null;
      },

      get bpm() {
        return bpm;
      },
      get running() {
        return running;
      },
      get lateBars() {
        return lateBars;
      },

      // Where the music is at an audio-clock time, for the screen and the judge.
      barAt(time) {
        for (const b of queued) {
          if (time >= b.start && time < b.end) return { index: b.index, pass: b.pass, beat: (time - b.start) / b.secondsPerBeat };
        }
        return null;
      },
    };
  }

  return { createScheduler, MIN_BPM, MAX_BPM, LOOKAHEAD };
});
