// improv: the Practice screen. Browser glue only: read the practice report and draw it as text.
// The words live in practice.js, which is tested under Node.
(function () {
  "use strict";
  const P = window.ImprovPractice;
  const W = window.ImprovWorkout;
  const $ = (id) => document.getElementById(id);
  const host = $("practice");
  const say = (text) => ($("practice-status").textContent = text);

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function draw(report) {
    $("practice-goal").textContent = P.goalLine(report);
    $("practice-streak").textContent = P.streakLine(report);
    $("practice-best").textContent = P.bestLine(report);
    $("practice-zone").textContent = `Your days run on ${report.timezone} time.`;
    const list = $("practice-log");
    list.textContent = "";
    const rows = report.log.filter((row) => row.seconds > 0);
    for (const row of rows) {
      const words = P.logRow(row);
      const li = make("li", "im-take");
      li.dataset.date = row.date;
      li.dataset.met = words.met ? "yes" : "no";
      const head = make("div", "im-take-head");
      head.appendChild(make("span", "im-take-title", words.day));
      head.appendChild(make("span", "im-take-when", [words.minutes, words.sessions].filter(Boolean).join(", ")));
      if (words.met) head.appendChild(make("span", "im-state im-state-done", "Goal met"));
      li.appendChild(head);
      list.appendChild(li);
    }
    $("practice-empty").hidden = rows.length > 0;
  }

  function drawWorkout(workout) {
    $("workout-status").textContent = W.summaryLine(workout);
    const list = $("workout-list");
    list.textContent = "";
    for (const item of workout.items) {
      const li = make("li", "im-take");
      li.dataset.exercise = item.exercise;
      li.dataset.slot = item.slot;
      li.dataset.done = item.done_today ? "yes" : "no";
      const head = make("div", "im-take-head");
      head.appendChild(make("span", "im-take-title", item.title));
      if (item.lesson_title) head.appendChild(make("span", "im-take-when", item.lesson_title));
      if (item.done_today) head.appendChild(make("span", "im-state im-state-done", "Done today"));
      li.appendChild(head);
      li.appendChild(make("p", "im-note", W.reason(item)));
      const play = make("a", "im-btn im-btn-link", W.playLabel(item));
      play.dataset.keyItem = "yes";
      play.href = W.playUrl(host.dataset.playUrl, item);
      li.appendChild(play);
      list.appendChild(li);
    }
    $("workout-empty").hidden = workout.total > 0;
  }

  async function read(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  async function init() {
    try {
      draw(await read(host.dataset.apiPractice));
      say("");
    } catch (e) {
      say("Your practice could not be loaded. " + e.message);
    }
    try {
      drawWorkout(await read(host.dataset.apiWorkout));
    } catch (e) {
      $("workout-status").textContent = "The workout could not be loaded. " + e.message;
    }
  }

  if (!P || !W) say("The page's scripts did not load.");
  else init();
})();
