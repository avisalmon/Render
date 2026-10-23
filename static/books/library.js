/* My library's rows (Avi, 2026-10-23): one box per book, "show", and when it is
   on, a small menu of how the book is offered (not offered, give, lend, swap,
   sell). Saved the moment it is touched, with no page reload, so a long list
   never jumps back to the top. The server answers with the row's whole state. */
(function () {
  "use strict";
  var csrf = document.body.getAttribute("data-csrf");
  var list = document.querySelector("[data-flag-list]");
  if (!list) return;

  var apply = function (box, state) {
    var show = box.querySelector("[data-flag-show]");
    var offer = box.querySelector("[data-flag-offer]");
    show.checked = !!state.show;
    show.disabled = false;
    offer.value = state.offer || "";
    offer.hidden = !state.show;
    offer.disabled = false;
    var row = box.closest("[data-copy-row]");
    var label = row && row.querySelector("[data-copy-status]");
    if (label && state.label !== undefined) label.textContent = state.label;
  };

  var save = function (box, flag, value, undo) {
    box.querySelectorAll("input, select").forEach(function (i) { i.disabled = true; });
    fetch(box.getAttribute("data-url"), {
      method: "POST", headers: {"Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": csrf},
      body: JSON.stringify({flag: flag, on: value}),
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
      .then(function (state) { apply(box, state); box.classList.add("is-saved"); setTimeout(function () { box.classList.remove("is-saved"); }, 900); })
      .catch(function () {
        undo();
        box.querySelectorAll("input, select").forEach(function (i) { i.disabled = false; });
        box.classList.add("is-failed"); setTimeout(function () { box.classList.remove("is-failed"); }, 1600);
      });
  };

  list.addEventListener("change", function (e) {
    var box = e.target.closest("[data-copy-flags]");
    if (!box) return;
    if (e.target.matches("[data-flag-show]")) {
      var input = e.target, was = !input.checked;
      save(box, "show", input.checked, function () { input.checked = was; });
    } else if (e.target.matches("[data-flag-offer]")) {
      var sel = e.target, before = sel.getAttribute("data-was") || "";
      save(box, "offer", sel.value, function () { sel.value = before; });
      sel.setAttribute("data-was", sel.value);
    }
  });
})();
