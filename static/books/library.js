/* My library's rows (Avi, 2026-10-23): every book carries four switches, show /
   give / lend / sell, saved the moment one is tapped, with no page reload, so a
   long list never jumps back to the top. The answer from the server sets all
   four (ticking "give" turns "show" on; unticking "show" turns the offers off). */
(function () {
  "use strict";
  var csrf = document.body.getAttribute("data-csrf");
  var list = document.querySelector("[data-flag-list]");
  if (!list) return;

  var apply = function (box, state) {
    box.querySelectorAll("[data-flag]").forEach(function (input) {
      input.checked = !!state[input.getAttribute("data-flag")];
      input.disabled = false;
    });
    var label = box.closest("[data-copy-row]");
    label = label && label.querySelector("[data-copy-status]");
    if (label && state.label !== undefined) label.textContent = state.label;
  };

  list.addEventListener("change", function (e) {
    var input = e.target.closest("[data-flag]");
    if (!input) return;
    var box = input.closest("[data-copy-flags]");
    var was = !input.checked;
    box.querySelectorAll("[data-flag]").forEach(function (i) { i.disabled = true; });
    fetch(box.getAttribute("data-url"), {
      method: "POST", headers: {"Content-Type": "application/json", "Accept": "application/json", "X-CSRFToken": csrf},
      body: JSON.stringify({flag: input.getAttribute("data-flag"), on: input.checked}),
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
      .then(function (state) { apply(box, state); box.classList.add("is-saved"); setTimeout(function () { box.classList.remove("is-saved"); }, 900); })
      .catch(function () {
        input.checked = was;
        box.querySelectorAll("[data-flag]").forEach(function (i) { i.disabled = false; });
        box.classList.add("is-failed"); setTimeout(function () { box.classList.remove("is-failed"); }, 1600);
      });
  });
})();
