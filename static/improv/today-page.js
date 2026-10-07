// improv: the Today screen. Browser glue only: read four derived endpoints and draw them as text.
// The words and the ring live in practice.js, workout.js and today.js, which run under Node.
(function () {
  "use strict";
  const P = window.ImprovPractice;
  const W = window.ImprovWorkout;
  const T = window.ImprovToday;
  const $ = (id) => document.getElementById(id);
  const host = $("today");
  const say = (text) => ($("today-status").textContent = text);

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function drawGoal(report) {
    $("today-goal").textContent = P.goalLine(report);
    $("today-streak").textContent = P.streakLine(report);
    const ring = $("today-ring");
    ring.style.setProperty("--pct", String(Math.round(T.ringFraction(report) * 100)));
    ring.dataset.met = report.goal_met ? "yes" : "no";
    ring.setAttribute("aria-label", `Daily goal: ${T.ringLabel(report)}`);
    $("today-ring-label").textContent = T.ringLabel(report);
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

  function drawContinue(next) {
    $("continue-line").textContent = T.continueLine(next);
    const link = $("continue-link");
    const goes = next.state === "continue" || next.state === "start";
    link.hidden = !goes;
    if (goes) {
      link.textContent = T.continueLabel(next);
      link.href = T.lessonUrl(host.dataset.lessonsUrl, next);
    }
  }

  async function read(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  async function init() {
    const failed = [];
    const run = async (name, url, draw, into) => {
      try {
        draw(await read(url));
      } catch (e) {
        failed.push(name);
        if (into) $(into).textContent = `The ${name} could not be loaded. ${e.message}`;
      }
    };
    await run("goal", host.dataset.apiPractice, drawGoal, "today-goal");
    await run("workout", host.dataset.apiWorkout, drawWorkout, "workout-status");
    await run("lessons", host.dataset.apiContinue, drawContinue, "continue-line");
    await run("level", host.dataset.apiSummary, (summary) => ($("today-level").textContent = T.levelLine(summary)), "today-level");
    say(failed.length ? "Some of today could not be loaded." : "");
  }

  if (!P || !W || !T) say("The page's scripts did not load.");
  else init();
})();
