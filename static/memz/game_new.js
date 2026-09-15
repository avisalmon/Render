(function () {
  "use strict";
  var form = document.querySelector("[data-new-session-form]");
  if (!form) return;

  var roundsInput = form.querySelector("[data-rounds-input]");
  var roundsValue = form.querySelector("[data-rounds-value]");
  roundsInput.addEventListener("input", function () { roundsValue.textContent = roundsInput.value; });

  var secondsInput = form.querySelector("[data-seconds-input]");
  var secondsValue = form.querySelector("[data-seconds-value]");
  secondsInput.addEventListener("input", function () { secondsValue.textContent = secondsInput.value; });

  var submitBtn = form.querySelector("[data-new-session-submit]");
  var errorEl = form.querySelector("[data-new-session-error]");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    errorEl.hidden = true;
    try {
      var data = await window.memz.api("POST", "/memz/api/sessions/", {
        round_count: parseInt(roundsInput.value, 10),
        round_seconds: parseInt(secondsInput.value, 10),
      });
      window.memz.setPlayerToken(data.code, data.token);
      window.location.href = "/memz/s/" + data.code + "/";
    } catch (err) {
      errorEl.textContent = (err.data && err.data.detail) || "לא הצלחנו לפתוח חדר, נסו שוב.";
      errorEl.hidden = false;
      submitBtn.disabled = false;
    }
  });
})();
