/* memz — the shared page helper (spec Rule 12.3.2): pages are consumers of
   the API. One CSRF read, one fetch wrapper that throws on a non-2xx, and
   a player-token hook for the game (SPR-Z.3). Nothing else lives here. */
(function () {
  "use strict";

  var csrf = document.body.getAttribute("data-csrf") || "";

  // A token is scoped to the one session it was issued for (spec Rule
  // 3.1.3), so the storage key carries the room code.
  function tokenKey(code) { return "memz.player." + String(code || "").toUpperCase(); }

  function getPlayerToken(code) {
    try {
      return window.localStorage.getItem(tokenKey(code)) || "";
    } catch (e) {
      return "";
    }
  }

  function setPlayerToken(code, token) {
    try {
      window.localStorage.setItem(tokenKey(code), token);
    } catch (e) { /* private mode or full storage: the tab still works this visit */ }
  }

  // ---- sound, haptics, and the mute toggle (spec §9.1, F-Z.6.2) ---------
  //
  // The toggle lives in the header on every page (base.html) so it is
  // available before a game even starts and persists across sessions.
  // Audio only plays once the browser has seen a user gesture on this
  // page — a game is never reached without tapping something first (join,
  // start, create), so that gesture is always already behind us by the
  // time a sound would play.

  var MUTE_KEY = "memz.muted";

  function isMuted() {
    try {
      return window.localStorage.getItem(MUTE_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function setMuted(muted) {
    try {
      window.localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
    } catch (e) { /* private mode: this tab just stays unmuted */ }
  }

  var soundCache = {};

  function playSound(name) {
    if (isMuted()) return;
    try {
      var audio = soundCache[name];
      if (!audio) {
        audio = new Audio("/static/memz/sound/" + name + ".wav");
        soundCache[name] = audio;
      }
      audio.currentTime = 0;
      audio.play().catch(function () { /* no gesture yet, or autoplay blocked: silent */ });
    } catch (e) { /* Audio unsupported: never break the page over a sound */ }
  }

  function vibrate(ms) {
    if (isMuted()) return;
    try {
      if (navigator.vibrate) navigator.vibrate(ms);
    } catch (e) { /* not every browser allows it; never surfaced as an error */ }
  }

  function updateMuteButton() {
    var btn = document.querySelector("[data-mute-toggle]");
    if (!btn) return;
    var muted = isMuted();
    btn.textContent = muted ? "🔇" : "🔊";
    btn.setAttribute("aria-pressed", muted ? "true" : "false");
  }

  document.addEventListener("DOMContentLoaded", function () {
    updateMuteButton();
    var btn = document.querySelector("[data-mute-toggle]");
    if (btn) {
      btn.addEventListener("click", function () {
        setMuted(!isMuted());
        updateMuteButton();
      });
    }
  });

  // ---- installable as a PWA (spec Rule 11.5, F-Z.6.7) -------------------
  //
  // Android/Chrome fire `beforeinstallprompt`; nothing here does that for
  // iOS Safari, which only ever offers "add to home screen" through its
  // own share sheet — so Safari gets a one-time dismissible hint instead
  // of a button that would never do anything.

  var deferredInstallPrompt = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredInstallPrompt = e;
  });

  function isIosSafariNotInstalled() {
    var ua = window.navigator.userAgent || "";
    var isIos = /iPhone|iPad|iPod/.test(ua);
    var isStandalone = window.navigator.standalone === true
      || window.matchMedia("(display-mode: standalone)").matches;
    return isIos && !isStandalone;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var tip = document.querySelector("[data-install-tip]");
    if (!tip) return;
    var dismissed = false;
    try { dismissed = window.localStorage.getItem("memz.installTipDismissed") === "1"; } catch (e) { /* ignore */ }
    if (!dismissed && isIosSafariNotInstalled()) tip.hidden = false;
    var dismissBtn = document.querySelector("[data-install-dismiss]");
    if (dismissBtn) {
      dismissBtn.addEventListener("click", function () {
        tip.hidden = true;
        try { window.localStorage.setItem("memz.installTipDismissed", "1"); } catch (e) { /* ignore */ }
      });
    }
  });

  async function api(method, url, body, playerToken) {
    var headers = { "Accept": "application/json", "X-CSRFToken": csrf };
    if (playerToken) headers["X-Memz-Player"] = playerToken;
    var options = { method: method, headers: headers, credentials: "same-origin" };
    if (body instanceof FormData) {
      options.body = body;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    var response = await fetch(url, options);
    var data = null;
    var type = response.headers.get("Content-Type") || "";
    if (type.indexOf("application/json") === 0) data = await response.json();
    if (!response.ok) {
      var error = new Error("memz api " + response.status + " " + url);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  // SPR-Z.11: the same "add your own photos" control now appears in three
  // places -- the home screen, the lobby, and the profile's bank tab --
  // so it lives here once instead of being written out three times and
  // drifting. `container` is any element; it gets a file input, a button
  // and a status line. `onUploaded(image)` is called per accepted file.
  function mountUploader(container, options) {
    if (!container || container.dataset.uploaderMounted === "1") return;
    container.dataset.uploaderMounted = "1";
    options = options || {};

    // ACT-Z.15 (Avi: "it needs to allow images from phone, real camera
    // and files"): two real buttons in the house style, each driving a
    // hidden file input, instead of the browser's own "Choose Files"
    // control. The camera input carries `capture`, which is what makes a
    // phone open the camera rather than a file browser; the gallery input
    // is `multiple`, which the camera one must not be (with `multiple`
    // set, iOS drops the camera option from its sheet). Picking is the
    // whole gesture: the upload starts on `change`, no second tap.
    container.innerHTML =
      '<input type="file" accept="image/*" capture="environment" data-uploader-camera hidden>' +
      '<input type="file" accept="image/*" multiple data-uploader-gallery hidden>' +
      '<div class="memz-uploader-buttons">' +
      '<button type="button" class="memz-btn memz-btn--secondary" data-uploader-take>מצלמים 📷</button>' +
      '<button type="button" class="memz-btn memz-btn--secondary" data-uploader-pick>מהגלריה</button>' +
      "</div>" +
      '<p class="memz-fineprint" data-uploader-status hidden></p>';

    var cameraInput = container.querySelector("[data-uploader-camera]");
    var galleryInput = container.querySelector("[data-uploader-gallery]");
    var buttons = container.querySelectorAll("button");
    var status = container.querySelector("[data-uploader-status]");

    function say(text) {
      status.textContent = text;
      status.hidden = !text;
    }

    function setBusy(busy) {
      buttons.forEach(function (b) { b.disabled = busy; });
    }

    async function uploadAll(input) {
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) return;
      setBusy(true);
      var done = 0;
      var failed = 0;
      for (var i = 0; i < files.length; i++) {
        say(files.length === 1 ? "מעלים..." : "מעלים " + (i + 1) + " מתוך " + files.length + "...");
        var body = new FormData();
        body.append("file", files[i]);
        try {
          var image = await api("POST", "/memz/api/images/", body);
          done += 1;
          if (options.onUploaded) options.onUploaded(image);
        } catch (e) {
          failed += 1;
          var detail = (e.data && (e.data.file || e.data.detail)) || "";
          if (detail) say(String(detail));
        }
      }
      input.value = "";
      setBusy(false);
      if (!failed) {
        // Rule 6.4.1: an upload is not usable until moderation passes it,
        // so "uploaded" is the honest word here, not "added to the game".
        say(done === 1 ? "תמונה אחת נוספה לבנק שלכם." : done + " תמונות נוספו לבנק שלכם.");
      } else if (done) {
        say(done + " נוספו, " + failed + " לא עברו.");
      }
    }

    container.querySelector("[data-uploader-take]").addEventListener("click", function () { cameraInput.click(); });
    container.querySelector("[data-uploader-pick]").addEventListener("click", function () { galleryInput.click(); });
    cameraInput.addEventListener("change", function () { uploadAll(cameraInput); });
    galleryInput.addEventListener("change", function () { uploadAll(galleryInput); });
  }

  window.memz = {
    csrf: csrf, api: api, getPlayerToken: getPlayerToken, setPlayerToken: setPlayerToken,
    isMuted: isMuted, setMuted: setMuted, playSound: playSound, vibrate: vibrate,
    mountUploader: mountUploader,
    deferredInstallPrompt: function () { return deferredInstallPrompt; },
  };
})();
