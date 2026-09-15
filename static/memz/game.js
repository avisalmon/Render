/* The one page for the whole game (spec §12.2): lobby, every round phase,
   results, podium. Reads static/memz/memz.js's `api()` helper and redraws
   from the state endpoint on a poll whose interval adapts to the phase
   (spec Rule 11.6). Screen-mode (the big screen, spec §4.10) is the same
   client with no token and no controls rendered. */
(function () {
  "use strict";

  var root = document.querySelector("[data-game-root]");
  if (!root) return;

  var code = root.dataset.code;
  var screenMode = root.dataset.screenMode === "1";
  var marker = document.querySelector("[data-screen]");
  var token = screenMode ? "" : window.memz.getPlayerToken(code);

  if (!screenMode && !token) {
    window.location.href = "/memz/join/" + encodeURIComponent(code) + "/";
    return;
  }

  var pollTimer = null;
  var busy = false;   // one action in flight at a time (spec Rule 11.1)

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setScreen(name) { if (marker) marker.dataset.screen = name; }

  function countdown(el, deadlineIso) {
    if (!deadlineIso) { el.textContent = ""; return; }
    var deadline = new Date(deadlineIso).getTime();
    function tick() {
      var left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      el.textContent = String(left);
      el.classList.toggle("memz-timer--urgent", left <= 5);
      if (left <= 0) { clearInterval(iv); }
    }
    tick();
    var iv = setInterval(tick, 250);
  }

  async function call(method, path, body) {
    return window.memz.api(method, "/memz/api/sessions/" + encodeURIComponent(code) + path, body, token);
  }

  async function guardedAction(fn) {
    if (busy) return;
    busy = true;
    try {
      var state = await fn();
      render(state);
    } catch (err) {
      var msg = (err && err.data && err.data.detail) || "לא הצלחנו, נסו שוב.";
      root.querySelector("[data-action-error]") && (root.querySelector("[data-action-error]").textContent = msg);
      window.alertless = msg; // never a native alert (spec Rule 11.1)
    } finally {
      busy = false;
    }
  }

  // ---------------------------------------------------------------- render

  function playerRow(p) {
    var dot = p.presence === "active" ? "🟢" : p.presence === "away" ? "🟡" : "⚪️";
    return (
      '<li class="memz-player-row' + (p.is_me ? " memz-player-row--me" : "") + '">' +
      '<span class="memz-presence-dot">' + dot + "</span>" +
      "<span>" + esc(p.nickname) + (p.is_host ? " 👑" : "") + "</span>" +
      '<span class="memz-player-score">' + p.score + "</span>" +
      "</li>"
    );
  }

  function renderLobby(state) {
    setScreen("game-lobby");
    var me = state.players.find(function (p) { return p.is_me; });
    var isHost = me && me.is_host;
    var canStart = state.can_start;
    root.innerHTML =
      '<h1 class="memz-title">החדר שלכם</h1>' +
      '<div class="memz-code-display">' + esc(state.code) + "</div>" +
      '<p class="memz-fineprint">שתפו את הקוד או את הקישור עם חברים.</p>' +
      '<ul class="memz-player-list">' + state.players.map(playerRow).join("") + "</ul>" +
      (isHost
        ? '<button class="memz-btn memz-btn--primary memz-btn--wide" data-start-btn' + (canStart ? "" : " disabled") + ">" +
          (canStart ? "מתחילים!" : "צריך עוד שחקנים (" + state.min_players + " לפחות)") + "</button>"
        : '<p class="memz-lead">מחכים שהמארח/ת יתחיל/תתחיל...</p>') +
      '<p class="memz-error" data-action-error></p>';
    if (isHost) {
      root.querySelector("[data-start-btn]").addEventListener("click", function () {
        guardedAction(function () { return call("POST", "/start/"); });
      });
    }
  }

  function renderCaptioning(state) {
    setScreen("game-captioning");
    var r = state.round;
    var mine = r.my_submission;
    var already = mine && mine.submitted;
    root.innerHTML =
      '<h1 class="memz-title">כותבים כיתוב</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count + "</p>" +
      '<div class="memz-round-timer" data-timer></div>' +
      (mine && mine.image_url ? '<img class="memz-result-image" src="' + esc(mine.image_url) + '" alt="">' : "") +
      (already
        ? '<p class="memz-lead">שלחתם! ' + r.submitted_count + "/" + r.total_count + " כבר שלחו." + "</p>"
        : '<form data-caption-form>' +
          '<textarea class="memz-input memz-textarea" maxlength="140" placeholder="הכיתוב שלכם..." data-caption-input></textarea>' +
          '<button class="memz-btn memz-btn--primary memz-btn--wide" type="submit">שולחים</button>' +
          "</form>") +
      '<p class="memz-error" data-action-error></p>';
    countdown(root.querySelector("[data-timer]"), r.caption_deadline);
    var form = root.querySelector("[data-caption-form]");
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = form.querySelector("[data-caption-input]").value;
        guardedAction(function () { return call("POST", "/rounds/" + r.number + "/submit/", { caption_text: text }); });
      });
    }
  }

  function renderRevealed(state) {
    setScreen("game-revealed");
    var r = state.round;
    var me = state.players.find(function (p) { return p.is_me; });
    root.innerHTML =
      '<h1 class="memz-title">רגע של חשיפה...</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count + "</p>" +
      '<div class="memz-timer" data-timer></div>' +
      '<div class="memz-meme-grid">' + r.memes.map(function (m) {
        return '<figure class="memz-meme-tile"><img src="' + esc(m.rendered_url) + '" alt=""></figure>';
      }).join("") + "</div>" +
      (me && me.is_host ? '<button class="memz-btn memz-btn--secondary memz-btn--wide" data-advance-btn>למעבר להצבעה</button>' : "");
    countdown(root.querySelector("[data-timer]"), r.reveal_deadline);
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }); });
  }

  function renderVoting(state) {
    setScreen("game-voting");
    var r = state.round;
    root.innerHTML =
      '<h1 class="memz-title">למי הכי מצחיק?</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count + "</p>" +
      '<div class="memz-timer" data-timer></div>' +
      '<div class="memz-meme-grid">' + r.memes.map(function (m) {
        var mine = m.is_mine;
        var votedThis = r.my_vote === m.submission_id;
        return (
          '<figure class="memz-meme-tile' + (mine ? " memz-meme-tile--mine" : "") +
          (votedThis ? " memz-meme-tile--voted" : "") + '" data-vote-tile="' + m.submission_id + '">' +
          '<img src="' + esc(m.rendered_url) + '" alt="">' +
          (mine ? '<figcaption>שלכם</figcaption>' : votedThis ? '<figcaption>ההצבעה שלכם</figcaption>' : "") +
          "</figure>"
        );
      }).join("") + "</div>" +
      '<p class="memz-error" data-action-error></p>';
    countdown(root.querySelector("[data-timer]"), r.vote_deadline);
    if (!r.my_vote) {
      root.querySelectorAll("[data-vote-tile]").forEach(function (tile) {
        if (tile.classList.contains("memz-meme-tile--mine")) return;
        tile.addEventListener("click", function () {
          var id = parseInt(tile.dataset.voteTile, 10);
          guardedAction(function () { return call("POST", "/rounds/" + r.number + "/vote/", { submission_id: id }); });
        });
      });
    }
  }

  function renderResult(state) {
    setScreen("game-result");
    var r = state.round;
    var me = state.players.find(function (p) { return p.is_me; });
    var isLast = r.number >= state.round_count;
    root.innerHTML =
      '<h1 class="memz-title">תוצאות הסבב</h1>' +
      '<div class="memz-meme-grid">' + r.results.map(function (row) {
        return (
          '<figure class="memz-meme-tile' + (row.round_winner ? " memz-meme-tile--winner" : "") + '">' +
          '<img src="' + esc(row.rendered_url) + '" alt="">' +
          "<figcaption>" + (row.round_winner ? "👑 " : "") + esc(row.nickname) + " · " + row.votes + " קולות</figcaption>" +
          "</figure>"
        );
      }).join("") + "</div>" +
      '<h2 class="memz-field-label">טבלת מובילים</h2>' +
      '<ul class="memz-player-list">' + state.players.slice().sort(function (a, b) { return b.score - a.score; }).map(playerRow).join("") + "</ul>" +
      (me && me.is_host
        ? '<button class="memz-btn memz-btn--primary memz-btn--wide" data-advance-btn>' + (isLast ? "לתוצאות הסופיות" : "לסבב הבא") + "</button>"
        : '<p class="memz-lead">מחכים למארח/ת...</p>');
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }); });
  }

  function renderFinished(state) {
    setScreen("game-finished");
    var me = state.players.find(function (p) { return p.is_me; });
    var podium = state.podium || [];
    root.innerHTML =
      '<h1 class="memz-title">🎉 נגמר!</h1>' +
      '<ol class="memz-podium">' + podium.map(function (row, i) {
        return "<li><b>#" + (i + 1) + "</b> " + esc(row.nickname) + " — " + row.score +
          (row.tied_with_next ? " (תיקו)" : "") + "</li>";
      }).join("") + "</ol>" +
      '<h2 class="memz-field-label">כל הממים</h2>' +
      '<div class="memz-meme-grid">' + (state.gallery || []).map(function (g) {
        return (
          '<figure class="memz-meme-tile"><img src="' + esc(g.rendered_url) + '" alt="">' +
          '<figcaption>' + esc(g.nickname) + "</figcaption>" +
          '<a class="memz-btn memz-btn--ghost memz-btn--small" href="/memz/m/' + esc(g.share_slug) + '/">שיתוף</a>' +
          "</figure>"
        );
      }).join("") + "</div>" +
      '<div class="memz-actions">' +
      (me && me.is_host ? '<button class="memz-btn memz-btn--primary" data-again-btn>עוד סבב</button>' : "<span></span>") +
      '<a class="memz-btn memz-btn--secondary" href="/memz/">לדף הראשי</a>' +
      "</div>";
    var again = root.querySelector("[data-again-btn]");
    if (again) again.addEventListener("click", function () { guardedAction(function () { return call("POST", "/again/"); }); });
  }

  function renderScreenMode(state) {
    // The TV/laptop view: read-only, larger, no per-player controls.
    if (state.status === "lobby") return renderLobby(state);
    var r = state.round;
    if (!r) return;
    if (r.status === "captioning") {
      setScreen("game-lobby");
      root.innerHTML = '<h1 class="memz-title">כותבים...</h1><p class="memz-lead">' + r.submitted_count + "/" + r.total_count + " כבר שלחו.</p>";
    } else if (r.status === "revealed") {
      renderRevealed(state);
    } else if (r.status === "voting") {
      setScreen("game-voting");
      root.innerHTML = '<h1 class="memz-title">מצביעים...</h1>' +
        '<p class="memz-lead">סבב ' + r.number + " מתוך " + state.round_count + " · " + state.players.length + " שחקנים בחדר</p>" +
        '<div class="memz-meme-grid">' +
        r.memes.map(function (m) { return '<figure class="memz-meme-tile"><img src="' + esc(m.rendered_url) + '" alt=""></figure>'; }).join("") +
        "</div>";
    } else {
      renderResult(state);
    }
  }

  function render(state) {
    if (screenMode) {
      if (state.status === "finished") renderFinished(state);
      else renderScreenMode(state);
      schedulePoll(state);
      return;
    }

    if (state.status === "finished" && state.next_session) {
      window.memz.setPlayerToken(state.next_session.code, state.next_session.token);
      window.location.href = "/memz/s/" + state.next_session.code + "/";
      return;
    }

    if (state.status === "lobby") renderLobby(state);
    else if (state.status === "playing") {
      var r = state.round;
      if (r.status === "captioning") renderCaptioning(state);
      else if (r.status === "revealed") renderRevealed(state);
      else if (r.status === "voting") renderVoting(state);
      else renderResult(state);
    } else {
      renderFinished(state);
    }
    schedulePoll(state);
  }

  function pollInterval(state) {
    var ms = { lobby: 2000, captioning: 1000, revealed: 1000, voting: 1000, done: 2000, finished: 5000 };
    var key = state.status === "playing" && state.round ? state.round.status : state.status;
    return ms[key] || 2000;
  }

  function schedulePoll(state) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, pollInterval(state));
  }

  async function poll() {
    try {
      var state = await window.memz.api("GET", "/memz/api/sessions/" + encodeURIComponent(code) + "/state/", undefined, token);
      render(state);
    } catch (err) {
      schedulePollRetry();
    }
  }

  function schedulePollRetry() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, 3000);
  }

  poll();
})();
