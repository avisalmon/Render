// improv: the Challenges screen. Browser glue only: read the bests and draw them as text.
// The words live in bests.js, which is tested under Node.
(function () {
  "use strict";
  const B = window.ImprovBests;
  const $ = (id) => document.getElementById(id);
  const host = $("challenges");
  const say = (text) => ($("challenges-status").textContent = text);

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function row(item) {
    const li = make("li", "im-take");
    li.dataset.exercise = item.exercise;
    li.dataset.passed = item.passed ? "yes" : "no";
    const head = make("div", "im-take-head");
    head.appendChild(make("span", "im-take-title", item.title));
    head.appendChild(make("span", "im-take-when", item.lesson_title || B.kindWords(item)));
    if (item.passed) head.appendChild(make("span", "im-state im-state-done", "Passed"));
    li.appendChild(head);
    const tries = B.attemptsLine(item);
    li.appendChild(make("p", "im-note", [B.scoreLine(item), tries].filter(Boolean).join(" ")));
    const play = make("a", "im-btn im-btn-link", B.playLabel(item));
    play.href = B.playUrl(host.dataset.playUrl, item);
    li.appendChild(play);
    return li;
  }

  function fill(list, items) {
    list.textContent = "";
    for (const item of items) list.appendChild(row(item));
  }

  function draw(data) {
    const parts = B.split(data.items);
    fill($("challenges-list"), parts.challenges);
    fill($("lessons-bests"), parts.lessons);
    $("challenges-empty").hidden = parts.challenges.length > 0;
    $("lessons-bests-empty").hidden = parts.lessons.length > 0;
    say(B.statusLine(data.items));
  }

  async function init() {
    try {
      const response = await fetch(host.dataset.apiBests, { credentials: "same-origin", headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`${response.status}`);
      draw(await response.json());
    } catch (e) {
      say("The challenges could not be loaded. " + e.message);
    }
  }

  if (!B) say("The page's scripts did not load.");
  else init();
})();
