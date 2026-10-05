// improv: the practice timer and the words about practice. Pure: no browser, runs under Node.
//
// The timer counts time the band was running or a note was played in the last ten seconds, not
// time the tab was open (spec ch. 6). The page reports it every thirty seconds and starts a new
// sitting after thirty idle minutes. The streak and the log are the server's reads; this file
// only says them in words.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovPractice = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const ACTIVE_WINDOW_MS = 10 * 1000;
  const REPORT_EVERY_MS = 30 * 1000;
  const IDLE_MS = 30 * 60 * 1000;

  // A clock fed with the moments that matter, in milliseconds on any one monotonic scale.
  // Between two moments nothing changes except a note's ten seconds running out, so the total is
  // the band's running time plus the stretches covered by a note's window, counted once.
  function createClock() {
    let running = false;
    let cursor = null;
    let lastNote = null;
    let totalMs = 0;

    function advance(now) {
      if (cursor === null) {
        cursor = now;
        return;
      }
      if (now <= cursor) return;
      if (running) totalMs += now - cursor;
      else if (lastNote !== null) totalMs += Math.max(0, Math.min(now, lastNote + ACTIVE_WINDOW_MS) - cursor);
      cursor = now;
    }

    return {
      bandStarted(now) {
        advance(now);
        running = true;
      },
      bandStopped(now) {
        advance(now);
        running = false;
      },
      notePlayed(now) {
        advance(now);
        lastNote = now;
      },
      // Whole seconds counted up to `now`.
      seconds(now) {
        advance(now);
        return Math.round(totalMs / 1000);
      },
    };
  }

  function sittingIsOver(lastActiveMs, nowMs) {
    return nowMs - lastActiveMs >= IDLE_MS;
  }

  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

  function goalLine(report) {
    if (report.goal_met) return `Today: goal met, ${plural(report.today_minutes, "minute", "minutes")}.`;
    return `Today: ${report.today_minutes} of ${plural(report.goal_minutes, "minute", "minutes")}.`;
  }

  function streakLine(report) {
    if (!report.streak) return "No streak yet. Meet the goal today to start one.";
    const days = `Streak: ${plural(report.streak, "day", "days")}.`;
    return report.goal_met ? days : `${days} Meet the goal today to keep it.`;
  }

  function bestLine(report) {
    return report.best_streak > report.streak ? `Best streak: ${plural(report.best_streak, "day", "days")}.` : "";
  }

  // "2026-10-05" read as a calendar date, never through the machine's own timezone.
  function logRow(row) {
    const [y, m, d] = row.date.split("-").map(Number);
    const weekday = WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
    return {
      day: `${weekday} ${d} ${MONTHS[m - 1]}`,
      minutes: row.seconds > 0 && row.minutes === 0 ? `${row.seconds} sec` : `${row.minutes} min`,
      sessions: row.sessions ? plural(row.sessions, "sitting", "sittings") : "",
      met: row.goal_met,
    };
  }

  return { ACTIVE_WINDOW_MS, REPORT_EVERY_MS, IDLE_MS, createClock, sittingIsOver, goalLine, streakLine, bestLine, logRow };
});
