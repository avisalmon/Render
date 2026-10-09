// improv: the Lessons screen. Browser glue only: list the lessons by level, in the order of the
// path. The rules live in lessons.js, which is tested under Node. Only text is ever put on the page.
(function () {
  "use strict";
  const L = window.ImprovLessons;
  const $ = (id) => document.getElementById(id);
  const host = $("lessons");
  const say = (text) => ($("lessons-status").textContent = text);

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  async function getJson(url) {
    const response = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`${url} answered ${response.status}`);
    return response.json();
  }

  function card(lesson, all, keyed) {
    const li = make("li", "im-take");
    li.dataset.slug = lesson.slug;
    li.dataset.state = lesson.state || "";
    if (lesson.current) li.dataset.current = "yes";
    const head = make("div", "im-take-head");
    head.appendChild(make("span", "im-take-title", lesson.title));
    if (lesson.current) head.appendChild(make("span", "im-state im-state-here", "You are here"));
    const label = L.stateLabel(lesson);
    if (label) head.appendChild(make("span", lesson.state === "done" ? "im-state im-state-done" : "im-state", label));
    li.appendChild(head);
    li.appendChild(make("p", "im-take-summary", `${L.describe(lesson, all)} ${lesson.summary}`));
    if (lesson.state === "ahead") li.appendChild(make("p", "im-note", L.aheadNote(lesson, all)));
    const actions = make("div", "im-card-actions");
    const open = make("a", "im-btn im-btn-link", "Open the lesson");
    if (keyed) open.dataset.keyItem = "yes";
    open.href = host.dataset.lessonUrl + encodeURIComponent(lesson.slug) + "/";
    actions.appendChild(open);
    li.appendChild(actions);
    return li;
  }

  // The piano key opens the lesson the player is at, else the first one not yet done.
  function keyedSlug(lessons) {
    const here = lessons.find((l) => l.current);
    if (here) return here.slug;
    const next = [...lessons].sort(L.byPath).find((l) => l.state !== "done");
    return next ? next.slug : null;
  }

  function draw(lessons) {
    const box = $("lessons-tracks");
    box.textContent = "";
    const keyed = keyedSlug(lessons);
    for (const group of L.groupByLevel(lessons)) {
      const section = make("section", "im-panel");
      section.setAttribute("aria-label", group.label);
      section.dataset.level = String(group.level);
      section.appendChild(make("h2", "im-h2", group.label));
      const list = make("ul", "im-takes-list");
      for (const lesson of group.lessons) list.appendChild(card(lesson, lessons, lesson.slug === keyed));
      section.appendChild(list);
      box.appendChild(section);
    }
  }

  async function init() {
    let lessons;
    try {
      lessons = await getJson(host.dataset.apiLessons);
    } catch (e) {
      say("The lessons could not be loaded. " + e.message);
      return;
    }
    draw(lessons);
    try {
      const summary = await getJson(host.dataset.apiSummary);
      $("lessons-level").textContent = L.levelLine(summary);
      $("lessons-done").textContent = L.lessonsDoneLine(summary);
    } catch (e) {
      // The lessons are still readable without the totals.
    }
    say(lessons.length ? `${lessons.length} ${lessons.length === 1 ? "lesson" : "lessons"}.` : "No lessons yet. Run seed_improv_lessons.");
  }

  if (!L) say("The page's scripts did not load.");
  else init();
})();
