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
  var gameModeInput = form.querySelector("[data-game-mode]");
  var captionModeInput = form.querySelector("[data-caption-mode]");
  var scoringField = form.querySelector("[data-scoring-field]");
  var deckField = form.querySelector("[data-deck-field]");

  function syncVisibility() {
    if (scoringField) scoringField.hidden = gameModeInput.value === "relaxed";
    if (deckField) deckField.hidden = captionModeInput.value !== "cards";
  }
  gameModeInput.addEventListener("change", syncVisibility);
  captionModeInput.addEventListener("change", syncVisibility);
  syncVisibility();

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    errorEl.hidden = true;
    try {
      var deckField2 = form.querySelector('[name="deck"]');
      var data = await window.memz.api("POST", "/memz/api/sessions/", {
        round_count: parseInt(roundsInput.value, 10),
        round_seconds: parseInt(secondsInput.value, 10),
        game_mode: gameModeInput.value,
        caption_mode: captionModeInput.value,
        scoring_mode: form.querySelector('[name="scoring_mode"]').value,
        deck: deckField2 ? deckField2.value : undefined,
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
