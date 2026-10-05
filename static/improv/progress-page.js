// improv: the Progress screen. Browser glue only: read four derived endpoints and draw them as text
// and a calendar of plain cells. The words live in today.js, weakness.js and bests.js (under Node).
(function () {
  "use strict";
  const P = window.ImprovPractice;
  const K = window.ImprovWeakness;
  const B = window.ImprovBests;
  const T = window.ImprovToday;
  const $ = (id) => document.getElementById(id);
  const host = $("progress");
  const say = (text) => ($("progress-status").textContent = text);
  const MOST_BESTS = 5;
  const CALENDAR_DAYS = T ? T.CALENDAR_WEEKS * 7 : 35;

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function drawLevel(summary) {
    $("progress-level").textContent = T.levelLine(summary);
    $("progress-lessons").textContent = T.lessonsLine(summary);
    const bar = T.levelBar(summary);
    const meter = $("progress-xp");
    meter.hidden = bar === null;
    if (bar) {
      meter.max = bar.max;
      meter.value = bar.value;
    }
  }

  function drawPractice(report) {
    $("progress-streak").textContent = P.streakLine(report);
    $("progress-best-streak").textContent = P.bestLine(report);
    const weeks = T.calendar(report);
    const grid = $("progress-calendar");
    grid.textContent = "";
    for (const name of T.WEEKDAYS) grid.appendChild(make("span", "im-cal-head", name));
    for (const week of weeks) {
      for (const day of week) {
        const cell = make("span", "im-cal-day", String(day.day));
        cell.dataset.date = day.date;
        cell.dataset.state = day.state;
        if (day.today) cell.dataset.today = "yes";
        cell.title = day.label;
        cell.setAttribute("aria-label", day.label);
        grid.appendChild(cell);
      }
    }
    $("progress-calendar-line").textContent = T.calendarLine(weeks);
  }

  function drawWeakness(report) {
    $("weakness-status").textContent = K.statusLine(report);
    const list = $("weakness-list");
    list.textContent = "";
    for (const claim of report.claims) {
      const li = make("li", "im-take");
      li.dataset.area = claim.area;
      if (claim.family) li.dataset.family = claim.family;
      const head = make("div", "im-take-head");
      head.appendChild(make("span", "im-take-title", K.claimLine(claim)));
      li.appendChild(head);
      li.appendChild(make("p", "im-note", K.evidenceLine(claim)));
      if (claim.exercise) {
        const play = make("a", "im-btn im-btn-link", K.playLabel(claim));
        play.href = K.playUrl(host.dataset.playUrl, claim);
        li.appendChild(play);
      } else {
        li.appendChild(make("p", "im-note", K.noExerciseLine(claim)));
      }
      list.appendChild(li);
    }
  }

  function drawBests(report) {
    const best = B.top(report.items, MOST_BESTS);
    $("bests-status").textContent = B.statusLine(report.items);
    const list = $("bests-list");
    list.textContent = "";
    for (const item of best) {
      const li = make("li", "im-take");
      li.dataset.exercise = item.exercise;
      li.dataset.passed = item.passed ? "yes" : "no";
      const head = make("div", "im-take-head");
      head.appendChild(make("span", "im-take-title", item.title));
      head.appendChild(make("span", "im-take-when", item.is_challenge ? "Challenge" : item.lesson_title));
      if (item.passed) head.appendChild(make("span", "im-state im-state-done", "Passed"));
      li.appendChild(head);
      li.appendChild(make("p", "im-note", [B.scoreLine(item), B.attemptsLine(item)].filter(Boolean).join(" ")));
      list.appendChild(li);
    }
    $("bests-empty").hidden = best.length > 0;
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
        $(into).textContent = `The ${name} could not be loaded. ${e.message}`;
      }
    };
    await run("level", host.dataset.apiSummary, drawLevel, "progress-level");
    await run("practice", `${host.dataset.apiPractice}?days=${CALENDAR_DAYS}`, drawPractice, "progress-streak");
    await run("report", host.dataset.apiWeakness, drawWeakness, "weakness-status");
    await run("best takes", host.dataset.apiBests, drawBests, "bests-status");
    say(failed.length ? "Some of your progress could not be loaded." : "");
  }

  if (!P || !K || !B || !T) say("The page's scripts did not load.");
  else init();
})();
