// improv: the words and the shapes of the Today and Progress screens. Pure: no browser, runs under Node.
//
// The server says where the player stands (the goal, the streak, the level, the lesson to go on
// with); this file turns that into the ring, the calendar and the sentences, so the page script is
// only glue and both screens say the same thing.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovToday = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DAY_MS = 24 * 60 * 60 * 1000;
  const CALENDAR_WEEKS = 5;

  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

  // ------------------------------------------------------------------ the goal ring

  // How much of today's goal is done, 0 to 1. A goal of nothing reads as met, not as a division by zero.
  function ringFraction(report) {
    const goal = Number(report.goal_minutes) * 60;
    if (!(goal > 0)) return 1;
    return Math.max(0, Math.min(1, Number(report.today_seconds) / goal));
  }

  function ringLabel(report) {
    return report.goal_met ? "Goal met" : `${report.today_minutes} of ${report.goal_minutes} min`;
  }

  // ------------------------------------------------------------------ where to go on

  function continueLine(next) {
    if (!next || next.state === "none") return "No lessons are open yet.";
    if (next.state === "finished") return "Every lesson is done. The challenges and your own charts are still there.";
    if (next.state === "continue") return `${next.title}: ${next.exercises_done} of ${next.exercises_total} passed.`;
    return `Next up: ${next.title}.`;
  }

  function continueLabel(next) {
    if (next && next.state === "continue") return "Continue";
    return "Start";
  }

  function lessonUrl(lessonsUrl, next) {
    return `${lessonsUrl}${encodeURIComponent(next.lesson)}/`;
  }

  // ------------------------------------------------------------------ the level

  function levelLine(summary) {
    if (!summary) return "";
    const head = `Level ${summary.level}, ${summary.xp} XP`;
    if (summary.next_level_at === null || summary.next_level_at === undefined) return head + ".";
    return `${head}. ${summary.next_level_at - summary.xp} XP to level ${summary.level + 1}.`;
  }

  // The XP gained and the XP the level asks for, for a progress bar; null at the top level.
  function levelBar(summary) {
    if (!summary || summary.next_level_at === null || summary.next_level_at === undefined) return null;
    return { value: summary.xp - summary.level_floor, max: summary.next_level_at - summary.level_floor };
  }

  function lessonsLine(summary) {
    if (!summary || !summary.lessons_total) return "";
    return `${summary.lessons_done} of ${plural(summary.lessons_total, "lesson", "lessons")} done, ${plural(summary.exercises_done, "exercise", "exercises")} passed.`;
  }

  // ------------------------------------------------------------------ the calendar

  const parseDate = (iso) => {
    const [y, m, d] = String(iso).split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };

  const isoOf = (ms) => new Date(ms).toISOString().slice(0, 10);

  // Five weeks, Monday first, the last one holding today. Each day is "met" (the goal was met),
  // "practised" (some practice, short of the goal), "rest" (none) or "future" (later this week).
  // Days are read as calendar dates, never through the machine's own timezone.
  function calendar(report, weeks) {
    const count = weeks || CALENDAR_WEEKS;
    const today = parseDate(report.today);
    const weekday = (new Date(today).getUTCDay() + 6) % 7;
    const start = today - (weekday + (count - 1) * 7) * DAY_MS;
    const byDate = new Map((report.log || []).map((row) => [row.date, row]));
    const rows = [];
    for (let w = 0; w < count; w += 1) {
      const row = [];
      for (let d = 0; d < 7; d += 1) {
        const ms = start + (w * 7 + d) * DAY_MS;
        const date = isoOf(ms);
        const found = byDate.get(date);
        let state = "rest";
        if (ms > today) state = "future";
        else if (found && found.goal_met) state = "met";
        else if (found && found.seconds > 0) state = "practised";
        const day = new Date(ms).getUTCDate();
        row.push({
          date,
          day,
          state,
          today: ms === today,
          minutes: found ? found.minutes : 0,
          label: cellLabel(ms, found, state),
        });
      }
      rows.push(row);
    }
    return rows;
  }

  function cellLabel(ms, found, state) {
    const d = new Date(ms);
    const name = `${WEEKDAYS[(d.getUTCDay() + 6) % 7]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
    if (state === "future") return name;
    if (state === "met") return `${name}: goal met, ${found.minutes} min`;
    if (state === "practised") return `${name}: ${found.seconds > 0 && found.minutes === 0 ? `${found.seconds} sec` : `${found.minutes} min`}`;
    return `${name}: no practice`;
  }

  // How many of the days shown had the goal met, for the line under the calendar.
  function calendarLine(weeks) {
    const days = weeks.flat().filter((c) => c.state !== "future");
    const met = days.filter((c) => c.state === "met").length;
    return `${met} of the last ${days.length} days met the goal.`;
  }

  return {
    WEEKDAYS,
    CALENDAR_WEEKS,
    ringFraction,
    ringLabel,
    continueLine,
    continueLabel,
    lessonUrl,
    levelLine,
    levelBar,
    lessonsLine,
    calendar,
    calendarLine,
  };
});
