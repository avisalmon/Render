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
  // A logged-in visitor with no token in *this* browser (spec §4.8.2 — a
  // different device, "My games" days later) gets it handed back by the
  // page itself, server-side, rather than being sent to /join/.
  var token = screenMode ? "" : (window.memz.getPlayerToken(code) || root.dataset.recoveredToken || "");

  if (!screenMode && !token) {
    window.location.href = "/memz/join/" + encodeURIComponent(code) + "/";
    return;
  }
  if (!screenMode && token) window.memz.setPlayerToken(code, token);

  var isAuthenticated = document.body.getAttribute("data-authenticated") === "1";
  if (!screenMode && token && isAuthenticated) {
    // Rule 3.3.5: a guest who is (or just became) signed in gets this seat
    // linked to their account. Idempotent for the same account, silently
    // ignored (never surfaced as an error) if it belongs to someone else —
    // that only happens from a stray token, not a mistake the visitor made.
    call("POST", "/attach/").catch(function () {});
  }

  var pollTimer = null;
  var busy = false;   // one action in flight at a time (spec Rule 11.1)

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setScreen(name) { if (marker) marker.dataset.screen = name; }

  // spec Rule 4.4.3, and its own worked example for tone (§9.1): a player
  // who ran the clock out without submitting still sees the round through,
  // just told plainly and kindly that this one wasn't theirs.
  function missedThisRound(r) {
    if (screenMode || !r.memes) return false;
    return !r.memes.some(function (m) { return m.is_mine; });
  }

  function countdown(el, deadlineIso) {
    if (!deadlineIso) { el.textContent = ""; return; }
    var deadline = new Date(deadlineIso).getTime();
    var announced5s = false;   // the moment at 5s left is a one-time beat, not every tick (Rule 4.4.4)
    function tick() {
      var left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      el.textContent = String(left);
      var urgent = left <= 5 && left > 0;
      el.classList.toggle("memz-timer--urgent", urgent);
      if (urgent) {
        window.memz.playSound("tick");
        if (!announced5s) { window.memz.vibrate(120); announced5s = true; }
      }
      if (left <= 0) { clearInterval(iv); }
    }
    tick();
    var iv = setInterval(tick, 1000);
  }

  async function call(method, path, body) {
    return window.memz.api(method, "/memz/api/sessions/" + encodeURIComponent(code) + path, body, token);
  }

  function setInFlight(el, inFlight) {
    // Not every control that can start an action is a <button> (a hand
    // card is a plain <li>, spec §5.2), so this can't lean on the native
    // `disabled` property alone.
    if (!el) return;
    if ("disabled" in el) el.disabled = inFlight;
    el.classList.toggle("memz-busy", inFlight);
  }

  async function guardedAction(fn, el) {
    // Rule 11.1: every control that hits the network disables itself until
    // the response returns. `busy` already stopped a second click from
    // doing anything; this makes that state visible, not just effective —
    // a control that *looks* tappable while a request is in flight is the
    // same defect the phone guard exists to catch (the_manager.md Step 4a).
    if (busy) return;
    busy = true;
    setInFlight(el, true);
    try {
      var state = await fn();
      render(state);   // a full re-render replaces `el`, so nothing to re-enable here
    } catch (err) {
      var msg = (err && err.data && err.data.detail) || "לא הצלחנו, נסו שוב.";
      root.querySelector("[data-action-error]") && (root.querySelector("[data-action-error]").textContent = msg);
      setInFlight(el, false);   // the render() that would have replaced it never happened
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
      (isAuthenticated ? "" : '<p class="memz-fineprint"><a href="/memz/login/?next=' +
        encodeURIComponent(window.location.pathname) + '">כניסה לחשבון</a> כדי לשמור ממים אחר כך.</p>') +
      '<p class="memz-error" data-action-error></p>';
    if (isHost) {
      var startBtn = root.querySelector("[data-start-btn]");
      startBtn.addEventListener("click", function () {
        guardedAction(function () { return call("POST", "/start/"); }, startBtn);
      });
    }
  }

  function renderCaptioning(state) {
    setScreen("game-captioning");
    var r = state.round;
    var mine = r.my_submission;
    var already = mine && mine.submitted;
    var cardsMode = state.caption_mode === "cards";
    root.innerHTML =
      '<h1 class="memz-title">כותבים כיתוב</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count +
      (r.topic ? " · הנושא: " + esc(r.topic) : "") + "</p>" +
      '<div class="memz-round-timer" data-timer></div>' +
      (mine && mine.image_url ? '<img class="memz-result-image" src="' + esc(mine.image_url) + '" alt="">' : "") +
      (already
        ? '<p class="memz-lead">שלחתם! ' + r.submitted_count + "/" + r.total_count + " כבר שלחו." + "</p>"
        : cardsMode
        ? '<ul class="memz-hand">' + (r.my_hand || []).map(function (c) {
            return '<li class="memz-hand-card" data-hand-card="' + c.hand_card_id + '">' + esc(c.text) + "</li>";
          }).join("") + "</ul>" +
          (r.can_swap_card ? '<button class="memz-btn memz-btn--ghost memz-btn--small" data-swap-btn>החלפת קלף אחד (פעם אחת במשחק)</button>' : "")
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
        var submitBtn = form.querySelector('button[type="submit"]');
        var text = form.querySelector("[data-caption-input]").value;
        guardedAction(function () { return call("POST", "/rounds/" + r.number + "/submit/", { caption_text: text }); }, submitBtn);
      });
    }
    root.querySelectorAll("[data-hand-card]").forEach(function (li) {
      li.addEventListener("click", function () {
        guardedAction(function () {
          return call("POST", "/rounds/" + r.number + "/submit/", { hand_card_id: parseInt(li.dataset.handCard, 10) });
        }, li);
      });
    });
    var swapBtn = root.querySelector("[data-swap-btn]");
    if (swapBtn) {
      swapBtn.addEventListener("click", function () {
        var first = root.querySelector("[data-hand-card]");
        if (!first) return;
        guardedAction(function () { return call("POST", "/cards/swap/", { hand_card_id: parseInt(first.dataset.handCard, 10) }); }, swapBtn);
      });
    }
  }

  var revealedRoundSeen = null;   // spec §9.1: the drumroll plays once per round, not once per poll

  function renderRevealed(state) {
    setScreen("game-revealed");
    var r = state.round;
    var me = state.players.find(function (p) { return p.is_me; });
    root.innerHTML =
      '<h1 class="memz-title">רגע של חשיפה...</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count +
      (r.topic ? " · הנושא: " + esc(r.topic) : "") + "</p>" +
      '<div class="memz-timer" data-timer></div>' +
      '<div class="memz-meme-grid">' + r.memes.map(function (m, i) {
        return '<figure class="memz-meme-tile" style="animation-delay:' + (i * 90) + 'ms"><img src="' + esc(m.rendered_url) + '" alt=""></figure>';
      }).join("") + "</div>" +
      (missedThisRound(r) ? '<p class="memz-fineprint">לא הספקת, קורה. בסבב הבא!</p>' : "") +
      (me && me.is_host ? '<button class="memz-btn memz-btn--secondary memz-btn--wide" data-advance-btn>למעבר להצבעה</button>' : "");
    countdown(root.querySelector("[data-timer]"), r.reveal_deadline);
    var revealKey = state.code + ":" + r.number;
    if (revealedRoundSeen !== revealKey) {
      revealedRoundSeen = revealKey;
      window.memz.playSound("drumroll");
    }
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }, btn); });
  }

  function renderVoting(state) {
    setScreen("game-voting");
    var r = state.round;
    var isJudgeMode = state.scoring_mode === "judge";
    var iAmJudge = isJudgeMode && r.judge && r.judge.is_me;
    var canTap = !isJudgeMode || iAmJudge;
    root.innerHTML =
      '<h1 class="memz-title">' + (isJudgeMode ? (iAmJudge ? "מי המנצח/ת?" : "השופט/ת מחליט/ה...") : "למי הכי מצחיק?") + "</h1>" +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count +
      (isJudgeMode && r.judge ? " · השופט/ת: " + esc(r.judge.nickname) : "") + "</p>" +
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
      (missedThisRound(r) ? '<p class="memz-fineprint">לא הספקת, קורה. בסבב הבא!</p>' : "") +
      '<p class="memz-error" data-action-error></p>';
    countdown(root.querySelector("[data-timer]"), r.vote_deadline);
    if (!r.my_vote && canTap) {
      root.querySelectorAll("[data-vote-tile]").forEach(function (tile) {
        if (tile.classList.contains("memz-meme-tile--mine")) return;
        tile.addEventListener("click", function () {
          var id = parseInt(tile.dataset.voteTile, 10);
          guardedAction(function () { return call("POST", "/rounds/" + r.number + "/vote/", { submission_id: id }); }, tile);
        });
      });
    }
  }

  var lastRanking = {};       // player_id -> rank (0 = first), from the previous result screen
  var lastRankingCode = null; // which session that ranking belongs to

  function animateCountUp(el, target) {
    if (target <= 0) { el.textContent = "0"; return; }
    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) { el.textContent = String(target); return; }
    var start = null;
    var duration = 500;
    function step(ts) {
      if (start === null) start = ts;
      var progress = Math.min(1, (ts - start) / duration);
      el.textContent = String(Math.round(progress * target));
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function renderResult(state) {
    setScreen("game-result");
    var r = state.round;
    var me = state.players.find(function (p) { return p.is_me; });
    var isLast = r.number >= state.round_count;
    var relaxed = state.game_mode === "relaxed";
    root.innerHTML =
      '<h1 class="memz-title">' + (relaxed ? "היה כיף!" : "תוצאות הסבב") + "</h1>" +
      '<div class="memz-meme-grid">' + r.results.map(function (row, i) {
        return (
          '<figure class="memz-meme-tile' + (!relaxed && row.round_winner ? " memz-meme-tile--winner" : "") +
          '" style="animation-delay:' + (i * 90) + 'ms">' +
          '<img src="' + esc(row.rendered_url) + '" alt="">' +
          "<figcaption>" + (!relaxed && row.round_winner ? "👑 " : "") + esc(row.nickname) +
          (relaxed ? "" : ' · <span data-vote-count="' + row.submission_id + '">0</span> קולות') + "</figcaption>" +
          "</figure>"
        );
      }).join("") + "</div>" +
      (relaxed ? "" :
        '<h2 class="memz-field-label">טבלת מובילים</h2>' +
        '<ul class="memz-player-list">' + rankedPlayerRows(state.players) + "</ul>") +
      (me && me.is_host
        ? '<button class="memz-btn memz-btn--primary memz-btn--wide" data-advance-btn>' + (isLast ? "לתוצאות הסופיות" : "לסבב הבא") + "</button>"
        : '<p class="memz-lead">מחכים למארח/ת...</p>');
    if (!relaxed) {
      r.results.forEach(function (row) {
        var el = root.querySelector('[data-vote-count="' + row.submission_id + '"]');
        if (el) animateCountUp(el, row.votes);
      });
    }
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }, btn); });
  }

  function rankedPlayerRows(players) {
    var ranked = players.slice().sort(function (a, b) { return b.score - a.score; });
    var newRanking = {};
    var html = ranked.map(function (p, i) {
      newRanking[p.id] = i;
      var move = "";
      if (lastRankingCode === code && Object.prototype.hasOwnProperty.call(lastRanking, p.id)) {
        var prev = lastRanking[p.id];
        if (prev > i) move = '<span class="memz-rank-move memz-rank-move--up">▲</span>';
        else if (prev < i) move = '<span class="memz-rank-move memz-rank-move--down">▼</span>';
      }
      return playerRow(p).replace("</li>", move + "</li>");
    }).join("");
    lastRanking = newRanking;
    lastRankingCode = code;
    return html;
  }

  var finishedCelebrated = null;   // one confetti burst per session, not per poll

  function spawnConfetti() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    var colours = ["#C7301F", "#FFD23F", "#2E86AB", "#1E7B34"];
    var layer = document.createElement("div");
    layer.className = "memz-confetti-layer";
    for (var i = 0; i < 24; i++) {
      var piece = document.createElement("span");
      piece.className = "memz-confetti-piece";
      // 8-90%, not 0-100: a rotating piece's bounding box is wider than the
      // piece itself, and one that starts flush with an edge swept past it
      // (the phone guard caught this at left=-3 before the margin was here).
      piece.style.left = (8 + Math.round(Math.random() * 82)) + "%";
      piece.style.background = colours[i % colours.length];
      piece.style.animationDelay = (Math.random() * 0.4) + "s";
      piece.style.animationDuration = (1.6 + Math.random() * 0.8) + "s";
      layer.appendChild(piece);
    }
    document.body.appendChild(layer);
    setTimeout(function () { layer.remove(); }, 2600);
  }

  function renderFinished(state) {
    setScreen("game-finished");
    if (finishedCelebrated !== state.code) {
      finishedCelebrated = state.code;
      spawnConfetti();
    }
    var me = state.players.find(function (p) { return p.is_me; });
    var podium = state.podium || [];
    root.innerHTML =
      '<h1 class="memz-title">🎉 נגמר!</h1>' +
      '<ol class="memz-podium">' + podium.map(function (row, i) {
        return "<li><b>#" + (i + 1) + "</b> " + esc(row.nickname) + " — " + row.score +
          (row.tied_with_next ? " (תיקו)" : "") +
          (row.title ? '<span class="memz-title-badge">' + esc(row.title) + "</span>" : "") + "</li>";
      }).join("") + "</ol>" +
      '<h2 class="memz-field-label">כל הממים</h2>' +
      '<div class="memz-meme-grid">' + (state.gallery || []).map(function (g) {
        return (
          '<figure class="memz-meme-tile"><img src="' + esc(g.rendered_url) + '" alt="">' +
          '<figcaption>' + esc(g.nickname) + "</figcaption>" +
          '<a class="memz-btn memz-btn--ghost memz-btn--small" href="/memz/m/' + esc(g.share_slug) + '/">שיתוף</a>' +
          (isAuthenticated ? '<button type="button" class="memz-btn memz-btn--ghost memz-btn--small" data-save-slug="' + esc(g.share_slug) + '">שמירה</button>' : "") +
          "</figure>"
        );
      }).join("") + "</div>" +
      '<div class="memz-actions">' +
      (me && me.is_host ? '<button class="memz-btn memz-btn--primary" data-again-btn>עוד סבב</button>' : "<span></span>") +
      '<a class="memz-btn memz-btn--secondary" href="/memz/">לדף הראשי</a>' +
      "</div>";
    var again = root.querySelector("[data-again-btn]");
    if (again) again.addEventListener("click", function () { guardedAction(function () { return call("POST", "/again/"); }, again); });

    root.querySelectorAll("[data-save-slug]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        btn.disabled = true;
        try {
          await window.memz.api("POST", "/memz/api/saved/", { share_slug: btn.dataset.saveSlug });
          btn.textContent = "נשמר ✓";
        } catch (e) {
          btn.disabled = false;
        }
      });
    });
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

  var connectionBanner = document.querySelector("[data-connection-banner]");

  async function poll() {
    try {
      var state = await window.memz.api("GET", "/memz/api/sessions/" + encodeURIComponent(code) + "/state/", undefined, token);
      if (connectionBanner) connectionBanner.hidden = true;
      render(state);
    } catch (err) {
      // Rule 11.5: a lost connection shows a banner and keeps polling —
      // never a dead page, never a native alert.
      if (connectionBanner) connectionBanner.hidden = false;
      schedulePollRetry();
    }
  }

  function schedulePollRetry() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, 3000);
  }

  poll();
})();
