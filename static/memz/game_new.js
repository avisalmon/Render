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
  var imageSourceInput = form.querySelector("[data-image-source]");
  var packsField = form.querySelector("[data-packs-field]");
  var packsList = form.querySelector("[data-packs-list]");
  var packsLoaded = false;

  function syncVisibility() {
    if (scoringField) scoringField.hidden = gameModeInput.value === "relaxed";
    if (deckField) deckField.hidden = captionModeInput.value !== "cards";
    if (packsField && imageSourceInput) {
      var needsPacks = imageSourceInput.value === "packs" || imageSourceInput.value === "mix";
      packsField.hidden = !needsPacks;
      if (needsPacks && !packsLoaded) loadPacks();
    }
  }
  gameModeInput.addEventListener("change", syncVisibility);
  captionModeInput.addEventListener("change", syncVisibility);
  if (imageSourceInput) imageSourceInput.addEventListener("change", syncVisibility);
  syncVisibility();

  async function loadPacks() {
    packsLoaded = true;
    try {
      var packs = await window.memz.api("GET", "/memz/api/packs/");
      packsList.innerHTML = packs.map(function (p) {
        return '<li class="memz-player-row"><label style="flex:1;display:flex;gap:8px;align-items:center;">' +
          '<input type="checkbox" name="pack_ids" value="' + p.id + '"> <span>' + p.name +
          ' (' + p.image_count + ')</span></label></li>';
      }).join("") || '<li class="memz-fineprint">אין עדיין חבילות. אפשר ליצור אחת בפרופיל.</li>';
    } catch (e) {
      packsList.innerHTML = '<li class="memz-fineprint">לא הצלחנו לטעון חבילות.</li>';
    }
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    submitBtn.disabled = true;
    errorEl.hidden = true;
    try {
      var deckField2 = form.querySelector('[name="deck"]');
      var packIds = Array.prototype.slice.call(form.querySelectorAll('[name="pack_ids"]:checked'))
        .map(function (el) { return parseInt(el.value, 10); });
      var data = await window.memz.api("POST", "/memz/api/sessions/", {
        round_count: parseInt(roundsInput.value, 10),
        round_seconds: parseInt(secondsInput.value, 10),
        game_mode: gameModeInput.value,
        caption_mode: captionModeInput.value,
        scoring_mode: form.querySelector('[name="scoring_mode"]').value,
        deck: deckField2 ? deckField2.value : undefined,
        image_source: imageSourceInput ? imageSourceInput.value : undefined,
        packs: packIds.length ? packIds : undefined,
        release_session_code: (form.querySelector('[name="release_session_code"]') || {}).value,
      });
      window.memz.setPlayerToken(data.code, data.token);
      window.location.href = "/memz/s/" + data.code + "/";
    } catch (err) {
      if (err.status === 409 && err.data && err.data.cap_reached && err.data.oldest_session) {
        var oldest = err.data.oldest_session;
        errorEl.innerHTML = "";
        var msg = document.createElement("span");
        msg.textContent = "הגעתם למכסת המשחקים השמורים. אפשר לשחרר את המשחק מ-" +
          new Date(oldest.created_at).toLocaleDateString("he-IL") + " ולהמשיך.";
        var releaseBtn = document.createElement("button");
        releaseBtn.type = "button";
        releaseBtn.className = "memz-btn memz-btn--secondary memz-btn--small";
        releaseBtn.textContent = "שחרור והמשך";
        releaseBtn.style.marginInlineStart = "8px";
        releaseBtn.addEventListener("click", function () {
          var hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.name = "release_session_code";
          hidden.value = oldest.code;
          form.appendChild(hidden);
          form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { cancelable: true }));
        });
        errorEl.appendChild(msg);
        errorEl.appendChild(releaseBtn);
      } else {
        errorEl.textContent = (err.data && err.data.detail) || "לא הצלחנו לפתוח חדר, נסו שוב.";
      }
      errorEl.hidden = false;
      submitBtn.disabled = false;
    }
  });
})();
