/* cohort: the two material shelves (REQ-C.35, C.36).

   Tabs that remember which shelf you were on; order changed by dragging the
   handle (mouse, pen or finger, all through pointer events) or by the arrows;
   every change saved at once through the API, with a toast and an undo.
   Dragging only starts on the handle, so on a phone the page still scrolls
   normally everywhere else. */

(function () {
  "use strict";

  var root = document.getElementById("cb-shelves");
  if (!root) return;

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function api(method, path, body) {
    return fetch("/cohort/api/" + path, {
      method: method, credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error((data && data.detail) || "לא נשמר. נסו שוב.");
        return data;
      });
    });
  }

  /* ---------- tabs ---------- */

  var tabs = Array.prototype.slice.call(root.querySelectorAll('[role="tab"]'));
  var stale = false;

  function show(name, focus) {
    if (name === "mine" && stale) { location.replace(location.pathname + "#mine"); location.reload(); return; }
    tabs.forEach(function (t) {
      var on = t.dataset.tab === name;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      document.getElementById("panel-" + t.dataset.tab).hidden = !on;
      if (on && focus) t.focus();
    });
    try { localStorage.setItem("cb-shelf", name); } catch (e) { /* private mode */ }
    if (history.replaceState) history.replaceState(null, "", location.pathname + (name === "mine" ? "#mine" : ""));
  }

  var first = location.hash === "#mine" ? "mine" : null;
  if (!first) { try { first = localStorage.getItem("cb-shelf"); } catch (e) { first = null; } }
  show(first === "mine" ? "mine" : "course");

  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { show(t.dataset.tab); });
    t.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      show(tabs[(i + 1) % tabs.length].dataset.tab, true);
    });
  });

  /* ---------- the toast ---------- */

  var toast = document.getElementById("cb-toast");
  var toastText = document.getElementById("cb-toast-text");
  var toastUndo = document.getElementById("cb-toast-undo");
  var toastTimer = null, undoFn = null;

  function say(text, undo) {
    toastText.textContent = text;
    undoFn = undo || null;
    toastUndo.hidden = !undo;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; undoFn = null; }, undo ? 6000 : 3500);
  }
  toastUndo.addEventListener("click", function () {
    var fn = undoFn;
    toast.hidden = true;
    undoFn = null;
    if (fn) fn();
  });

  /* ---------- order ---------- */

  function cards(list) { return Array.prototype.slice.call(list.querySelectorAll(":scope > .cb-material")); }
  function order(list) { return cards(list).map(function (c) { return c.dataset.id; }); }
  function same(a, b) { return a.join(",") === b.join(","); }

  function apply(list, ids) {
    ids.forEach(function (id) {
      var c = list.querySelector(':scope > .cb-material[data-id="' + id + '"]');
      if (c) list.appendChild(c);
    });
  }

  function save(list, before) {
    var after = order(list);
    if (same(before, after)) return;
    api("POST", "materials/reorder/", { shelf: list.dataset.shelf, order: after }).then(function () {
      say("הסדר נשמר", function () {
        apply(list, before);
        api("POST", "materials/reorder/", { shelf: list.dataset.shelf, order: before })
          .then(function () { say("הסדר הוחזר"); })
          .catch(function (err) { say(err.message); });
      });
    }).catch(function (err) {
      apply(list, before);
      say(err.message);
    });
  }

  // The arrows: one step at a time, for keyboards and for anybody who prefers them.
  root.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-move]");
    if (!btn) return;
    var card = btn.closest(".cb-material");
    var list = card.parentNode;
    var before = order(list);
    if (btn.dataset.move === "up" && card.previousElementSibling) {
      list.insertBefore(card, card.previousElementSibling);
    } else if (btn.dataset.move === "down" && card.nextElementSibling) {
      list.insertBefore(card.nextElementSibling, card);
    } else {
      return;
    }
    btn.focus();
    save(list, before);
  });

  // Dragging by the handle.
  var drag = null;

  function autoscroll() {
    if (!drag) return;
    var top = (document.querySelector(".cb-top") || { offsetHeight: 0 }).offsetHeight + 40;
    var bottom = window.innerHeight - 50;
    var y = drag.y, step = 0;
    if (y < top) step = -Math.min(22, (top - y) / 3 + 4);
    else if (y > bottom) step = Math.min(22, (y - bottom) / 3 + 4);
    if (step) { window.scrollBy(0, step); place(); }
    drag.raf = requestAnimationFrame(autoscroll);
  }

  function place() {
    drag.card.style.top = (drag.y - drag.offset) + "px";
    var others = cards(drag.list).filter(function (c) { return c !== drag.card; });
    var target = null;
    for (var i = 0; i < others.length; i++) {
      var r = others[i].getBoundingClientRect();
      if (drag.y < r.top + r.height / 2) { target = others[i]; break; }
    }
    if (target) drag.list.insertBefore(drag.holder, target);
    else drag.list.appendChild(drag.holder);
  }

  root.addEventListener("pointerdown", function (e) {
    var handle = e.target.closest(".cb-handle");
    if (!handle || (e.pointerType === "mouse" && e.button !== 0)) return;
    var card = handle.closest(".cb-material");
    var list = card.parentNode;
    if (!list.dataset.sortable) return;
    e.preventDefault();
    var r = card.getBoundingClientRect();
    var holder = document.createElement("div");
    holder.className = "cb-placeholder";
    holder.style.height = r.height + "px";
    list.insertBefore(holder, card);
    drag = { card: card, list: list, holder: holder, before: order(list), offset: e.clientY - r.top, y: e.clientY, id: e.pointerId };
    card.classList.add("is-dragging");
    card.style.width = r.width + "px";
    card.style.left = r.left + "px";
    card.style.top = r.top + "px";
    document.body.classList.add("cb-dragging");
    try { handle.setPointerCapture(e.pointerId); } catch (err) { /* not needed */ }
    drag.raf = requestAnimationFrame(autoscroll);
  });

  window.addEventListener("pointermove", function (e) {
    if (!drag || e.pointerId !== drag.id) return;
    e.preventDefault();
    drag.y = e.clientY;
    place();
  });

  function end(e) {
    if (!drag || e.pointerId !== drag.id) return;
    cancelAnimationFrame(drag.raf);
    var d = drag;
    drag = null;
    d.list.insertBefore(d.card, d.holder);
    d.holder.remove();
    d.card.classList.remove("is-dragging");
    document.body.classList.remove("cb-dragging");
    d.card.style.width = d.card.style.left = d.card.style.top = "";
    save(d.list, d.before);
  }
  window.addEventListener("pointerup", end);
  window.addEventListener("pointercancel", end);

  /* ---------- keep a course item on my shelf ---------- */

  root.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-keep]");
    if (!btn || btn.disabled) return;
    btn.disabled = true;
    api("POST", "materials/" + btn.dataset.keep + "/keep/").then(function (r) {
      btn.textContent = "נשמר אצלך";
      stale = true;
      if (r.created) {
        var count = document.getElementById("cb-mine-count");
        count.textContent = String(parseInt(count.textContent, 10) + 1);
      }
      say(r.created ? "נשמר בחומרים שלך" : "זה כבר נמצא בחומרים שלך");
    }).catch(function (err) { btn.disabled = false; say(err.message); });
  });
})();
