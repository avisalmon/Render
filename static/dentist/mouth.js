/* The mouth (spec Rule 5.2): one tap on a tooth opens its state, a second
 * tap on the same tooth records what is chosen. Everything works without
 * this file (each tooth is a link, the form is a form); this only saves
 * the round trip of the first tap and makes the second tap submit.
 */
(function () {
  "use strict";
  var panel = document.getElementById("tooth-panel");
  var form = document.getElementById("tooth-form");
  if (!panel || !form) return;
  var input = document.getElementById("tooth-input");
  var label = document.getElementById("tooth-label");
  var hint = document.getElementById("tooth-hint");
  var planTooth = document.getElementById("plan-tooth");

  function select(n) {
    input.value = n;
    label.textContent = n;
    if (planTooth && !planTooth.value) planTooth.value = n;
    hint.textContent = "Tap tooth " + n + " again to record.";
    panel.hidden = false;
    document.querySelectorAll(".dn-tooth").forEach(function (t) {
      var on = t.getAttribute("data-tooth") === String(n);
      t.classList.toggle("is-on", on);
      if (on) t.setAttribute("aria-current", "true"); else t.removeAttribute("aria-current");
    });
  }

  document.querySelectorAll(".dn-tooth[data-tooth]").forEach(function (tooth) {
    tooth.addEventListener("click", function (event) {
      var n = tooth.getAttribute("data-tooth");
      if (input.value === n && form.querySelector('input[name="condition"]:checked')) {
        event.preventDefault();
        form.requestSubmit ? form.requestSubmit() : form.submit();
        return;
      }
      event.preventDefault();
      select(n);
      // The history for this tooth lives on the server: fetch it on the
      // next full load; for now the panel shows the form at once.
      var url = new URL(tooth.href, location.href);
      history.replaceState(null, "", url.pathname + url.search);
      panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
})();
