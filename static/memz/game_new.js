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

  var boothNote = form.querySelector("[data-booth-note]");
  // Two elements (the picker and the line explaining it), so a nodelist.
  var imageSourceParts = form.querySelectorAll("[data-image-source-field]");

  function syncVisibility() {
    if (scoringField) scoringField.hidden = gameModeInput.value === "relaxed";
    if (deckField) deckField.hidden = captionModeInput.value !== "cards";
    // SPR-W.2: the photo booth brings its own pool, so the "where do the
    // pictures come from" picker is not merely irrelevant here, it would be
    // a control that appears to choose something and doesn't. Hide it and
    // say what happens instead.
    var isBooth = gameModeInput.value === "photo_booth";
    if (boothNote) boothNote.hidden = !isBooth;
    imageSourceParts.forEach(function (el) { el.hidden = isBooth; });
    if (packsField && imageSourceInput) {
      // SPR-Z.11: `mix` no longer means "own + packs" (it is the public
      // bank + everyone's uploads, packs optional), and it is now the
      // default -- so opening the create screen no longer unfolds a pack
      // picker nobody asked for. Only `packs` mode needs one.
      var needsPacks = !isBooth && imageSourceInput.value === "packs";
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
      // The whole row is the target, not the box inside it. A bare
      // checkbox renders at about 13x13 CSS px, which is a third of the
      // 44 px Rule 11.1 requires -- the one control in the app still
      // shipping that way, because `packs` mode has to be chosen before
      // the list even unfolds and no screen-contract row reached it.
      packsList.innerHTML = packs.map(function (p) {
        return '<li class="memz-pack-row"><label class="memz-pack-label">' +
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
      var aiField = form.querySelector('[name="ai_player_count"]');
      var nicknameField = form.querySelector("[data-nickname-input]");
      var data = await window.memz.api("POST", "/memz/api/sessions/", {
        nickname: nicknameField ? nicknameField.value.trim() : "",
        round_count: parseInt(roundsInput.value, 10),
        round_seconds: parseInt(secondsInput.value, 10),
        ai_player_count: aiField ? parseInt(aiField.value, 10) : 0,
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
