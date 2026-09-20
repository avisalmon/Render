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
  // SPR-W.4: the TV releases the 560px phone column and takes the wall.
  // Set as a class on the document rather than keyed off the `data-screen`
  // marker, which `setScreen` rewrites on every phase.
  if (screenMode) document.documentElement.classList.add("memz-tvmode");
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

  // 2026-09-16 QA fix (Avi: "הזמנים לא מתמהגים נכון" -- the timings
  // don't sync/behave correctly): every countdown, and the reveal
  // slideshow's own "which meme right now" index, compare a
  // server-issued deadline against `Date.now()` -- correct only if the
  // device's own clock happens to be right, which a phone's isn't
  // always (wrong timezone, no NTP sync, whatever). `state.server_time`
  // now rides along on every poll; `serverNow()` is `Date.now()`
  // corrected by this browser's own measured offset from it, so a
  // deadline comparison holds even when the device's clock doesn't.
  var serverClockOffsetMs = 0;

  function updateServerClockOffset(state) {
    if (!state || !state.server_time) return;
    serverClockOffsetMs = new Date(state.server_time).getTime() - Date.now();
  }

  function serverNow() {
    return Date.now() + serverClockOffsetMs;
  }

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
      var left = Math.max(0, Math.round((deadline - serverNow()) / 1000));
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
    var dot = p.is_ai ? "🤖" : p.presence === "active" ? "🟢" : p.presence === "away" ? "🟡" : "⚪️";
    return (
      '<li class="memz-player-row' + (p.is_me ? " memz-player-row--me" : "") + '">' +
      '<span class="memz-presence-dot">' + dot + "</span>" +
      "<span>" + esc(p.nickname) + (p.is_host ? " 👑" : "") + "</span>" +
      '<span class="memz-player-score">' + p.score + "</span>" +
      "</li>"
    );
  }

  // SPR-Z.11: the lobby's uploader lives outside `root` (see game.html) so
  // a poll-driven rebuild can't take a half-made file selection with it.
  // All this does is show it in the lobby and hide it once play starts --
  // mid-round is the wrong moment to be picking photos, and the images a
  // round deals are chosen when the round starts anyway.
  var lobbyUploadSection = document.querySelector("[data-lobby-upload]");

  function showLobbyUploader(show) {
    if (!lobbyUploadSection) return;
    lobbyUploadSection.hidden = !show;
    if (show && window.memz.mountUploader) {
      window.memz.mountUploader(
        lobbyUploadSection.querySelector("[data-lobby-uploader]"),
        { label: "הוספת תמונות שלי" }
      );
    }
  }

  // SPR-W.2: the photo booth's own camera section, same outside-the-root
  // treatment as the lobby's (see game.html). It is mounted once and only
  // toggled after that -- a booth poll lands every second and must not be
  // able to drop a photo that is mid-choose or mid-upload.
  var boothUploadSection = document.querySelector("[data-booth-upload]");

  function showBoothUploader(show, state) {
    if (!boothUploadSection) return;
    boothUploadSection.hidden = !show;
    if (show && window.memz.mountUploader) {
      window.memz.mountUploader(
        boothUploadSection.querySelector("[data-booth-uploader]"),
        {
          endpoint: "/memz/api/sessions/" + encodeURIComponent(code) + "/booth/photo/",
          token: token,
          cameraFirst: true,
          cameraLabel: "לצלם מישהו 📷",
          successText: function (n) {
            return n === 1 ? "תמונה אחת נכנסה למשחק." : n + " תמונות נכנסו למשחק.";
          },
          onUploaded: function () {
            window.memz.vibrate(40);
            window.memz.playSound("pop");
            poll();   // the counts on the screen behind this are now stale
          },
        }
      );
    }
  }

  // Built once per booth, then only its numbers are updated -- rebuilding
  // the markup every second would restart the countdown's interval and
  // throw away the camera buttons' focus.
  var boothRenderKey = null;
  var boothTimerDeadline = null;

  function renderBooth(state) {
    setScreen("game-booth");
    showLobbyUploader(false);
    var b = state.booth || {};
    if (boothRenderKey !== state.code) {
      boothRenderKey = state.code;
      root.innerHTML =
        '<h1 class="memz-title">צלמו את החדר!</h1>' +
        '<p class="memz-lead">כל אחד מצלם מישהו אחר בשולחן. התמונות האלה הן כל הממים של הערב.</p>' +
        '<p class="memz-timer" data-booth-timer></p>' +
        '<p class="memz-lead memz-booth-counts" data-booth-counts></p>' +
        // The consent line. This is the one mode where the pictures are of
        // people who are in the room, so it is not boilerplate: somebody
        // who does not want to be photographed has to be able to say so
        // before the shutter, and the screen is where they learn they can.
        '<p class="memz-fineprint">מצלמים רק את מי שמסכים. התמונות נשארות במשחק הזה בלבד, ' +
        "נמחקות בסופו, ולא נכנסות לבנק של אף אחד.</p>" +
        '<div data-booth-host></div>' +
        '<div data-booth-escape></div>' +
        '<p class="memz-error" data-action-error></p>';
      boothTimerDeadline = null;
    }

    // The booth's deadline moves when the room hasn't shot enough yet
    // (Rule 5.5.4), so the countdown is re-armed on a *new* deadline
    // rather than once at build time -- otherwise it would sit on 0 while
    // the server quietly handed the room another thirty seconds. Only on a
    // change: re-arming every poll would stack an interval a second.
    if (b.deadline && b.deadline !== boothTimerDeadline) {
      boothTimerDeadline = b.deadline;
      countdown(root.querySelector("[data-booth-timer]"), b.deadline);
    }

    var counts = root.querySelector("[data-booth-counts]");
    if (counts) {
      var mine = b.my_photos || 0;
      var per = b.per_player || 0;
      counts.textContent = (b.total_photos || 0) + " תמונות בחדר · לכם יש " + mine + " מתוך " + per +
        (mine >= per ? " (הגעתם למקסימום)" : "");
    }

    // Only the host's button is (re)rendered on a change of state, and only
    // when its *label* would change -- it is the one control here, and a
    // thumb resting on it must not have it swapped out from underneath.
    var hostSlot = root.querySelector("[data-booth-host]");
    if (hostSlot && b.is_host) {
      var enough = (b.total_photos || 0) >= (b.min_photos || 0);
      var label = enough ? "מתחילים לשחק!" : "צריך עוד תמונות (" + b.min_photos + " לפחות)";
      if (hostSlot.dataset.label !== label) {
        hostSlot.dataset.label = label;
        hostSlot.innerHTML = '<button class="memz-btn memz-btn--primary memz-btn--wide" data-booth-close' +
          (enough ? "" : " disabled") + ">" + label + "</button>";
        var closeBtn = hostSlot.querySelector("[data-booth-close]");
        closeBtn.addEventListener("click", function () {
          guardedAction(function () { return call("POST", "/booth/close/"); }, closeBtn);
        });
      }
    }

    // Rule 5.5.6: the escape. It appears only after the booth has already
    // run out of time once without enough photos -- a room on laptops, or
    // one that said no to being photographed, would otherwise sit in front
    // of a disabled button and a clock that keeps starting over.
    var escapeSlot = root.querySelector("[data-booth-escape]");
    if (escapeSlot && b.is_host && b.extended && !escapeSlot.dataset.shown) {
      escapeSlot.dataset.shown = "1";
      escapeSlot.innerHTML =
        '<p class="memz-fineprint">אין מצלמות, או שלא בא לכם להצטלם? אפשר לשחק רגיל.</p>' +
        '<button class="memz-btn memz-btn--secondary memz-btn--wide" data-booth-abandon>' +
        "לשחק עם התמונות הרגילות</button>";
      var abandonBtn = escapeSlot.querySelector("[data-booth-abandon]");
      abandonBtn.addEventListener("click", function () {
        guardedAction(function () { return call("POST", "/booth/abandon/"); }, abandonBtn);
      });
    }
    showBoothUploader(!screenMode, state);
  }

  function howToPlayCard(state) {
    if (screenMode) return "";
    var relaxed = state.game_mode === "relaxed";
    var judge = state.scoring_mode === "judge";
    var verdict = relaxed
      ? "רואים את כולם יחד, בלי ניקוד."
      : judge
      ? "השופט/ת של הסבב בוחר/ת מנצח, 3 נקודות."
      : "כל מם על המסך 10 שניות. אוהב = 2, ככה ככה = 1, פחות = 0.";
    return (
      '<div class="memz-howto" data-howto>' +
      '<p class="memz-howto-line"><b>1.</b> כל אחד מקבל תמונה וכותב לה כיתוב. לא אהבתם את התמונה? אפשר להחליף עד 3 פעמים.</p>' +
      '<p class="memz-howto-line"><b>2.</b> ' + verdict + "</p>" +
      '<p class="memz-howto-line"><b>3.</b> אף אחד לא יודע מי כתב מה. רק הטבלה יודעת מי מוביל.</p>' +
      "</div>"
    );
  }

  function renderLobby(state) {
    setScreen("game-lobby");
    showLobbyUploader(!screenMode);
    var me = state.players.find(function (p) { return p.is_me; });
    var isHost = me && me.is_host;
    var canStart = state.can_start;
    root.innerHTML =
      '<h1 class="memz-title">החדר שלכם</h1>' +
      '<div class="memz-code-display">' + esc(state.code) + "</div>" +
      '<img class="memz-qr" src="/memz/s/' + encodeURIComponent(state.code) + '/qr.png" width="160" height="160" alt="קוד QR להצטרפות">' +
      '<p class="memz-fineprint">שתפו את הקוד, את הקישור או את קוד ה-QR עם חברים.</p>' +
      // SPR-W.1 (F-W.1.5): how to play, in the one place everyone is
      // sitting together waiting. Three lines, not a tutorial -- and the
      // one fact no other screen states: what the buttons are worth.
      howToPlayCard(state) +
      // ACT-Z.15: a real link, not a window.open() -- inside an installed
      // PWA, and in more than one phone browser, a popup from a click is
      // blocked or lands on wa.me's "continue to chat" page instead of
      // the app. A link to wa.me is a universal link WhatsApp itself
      // claims, so it just opens. The click handler below upgrades it to
      // the native share sheet where the browser has one.
      (screenMode ? "" :
        '<a class="memz-btn memz-btn--secondary memz-btn--wide" data-whatsapp-share-btn href="' +
        esc(whatsappInviteUrl(state.code)) + '" target="_blank" rel="noopener">' +
        "שיתוף בוואטסאפ 💬</a>") +
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
    var whatsappBtn = root.querySelector("[data-whatsapp-share-btn]");
    if (whatsappBtn && navigator.share) {
      // The phone's own share sheet: WhatsApp is right there, and so is
      // everything else, and it works inside an installed PWA. A user
      // who dismisses it gets nothing else thrown at them; a browser
      // that refuses the call for any other reason falls back to the
      // link the anchor already carries.
      whatsappBtn.addEventListener("click", function (e) {
        e.preventDefault();
        var invite = inviteMessage(state.code);
        navigator.share({ title: "memz", text: invite.text, url: invite.url }).catch(function (err) {
          if (err && err.name === "AbortError") return;
          window.location.href = whatsappInviteUrl(state.code);
        });
      });
    }
  }

  function inviteMessage(code) {
    var url = window.location.origin + "/memz/join/" + encodeURIComponent(code) + "/";
    return { url: url, text: "בואו נשחק memz! קוד החדר: " + code };
  }

  function whatsappInviteUrl(code) {
    var invite = inviteMessage(code);
    return "https://wa.me/?text=" + encodeURIComponent(invite.text + "\n" + invite.url);
  }

  // 2026-09-16 QA fix (Avi, live-testing the real game): captioning polls
  // every second (schedulePoll/pollInterval below), and this render used
  // to rebuild the whole screen on every single poll -- including the
  // <textarea> a player might be mid-word in. On mobile that tears the
  // focused element out from under the keyboard, which dismisses it, and
  // a moment later the freshly-rebuilt (empty) textarea grabs no focus
  // back, so the keyboard just flickers open and shut and whatever was
  // typed is gone. Nothing in the not-yet-submitted, typed-caption view
  // actually depends on the poll tick (the timer ticks itself, client
  // side, via countdown() below; nothing else on that screen changes
  // until the round itself does) -- so once it's showing, further polls
  // for the same round in the same submitted-state are simply skipped.
  var captioningRenderKey = null;

  function renderCaptioning(state) {
    var r = state.round;
    var mine = r.my_submission;
    var already = mine && mine.submitted;
    var cardsMode = state.caption_mode === "cards";
    // The dealt image is part of the key from SPR-Z.10 on: swapping it
    // (Rule 4.4.5) has to redraw this screen, and nothing else about the
    // skip-the-rebuild fix above may change. Whatever was already typed
    // survives a swap by being re-filled below, on purpose -- you threw
    // back the picture, not your sentence.
    var key = r.number + ":" + already + ":" + cardsMode + ":" + (mine && mine.image_url) +
      ":" + r.image_swaps_left;
    if (key === captioningRenderKey) return;
    var typedBefore = (root.querySelector("[data-caption-input]") || {}).value || "";
    captioningRenderKey = key;

    setScreen("game-captioning");
    root.innerHTML =
      '<h1 class="memz-title">כותבים כיתוב</h1>' +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count +
      (r.topic ? " · הנושא: " + esc(r.topic) : "") + "</p>" +
      '<div class="memz-round-timer" data-timer></div>' +
      (mine && mine.image_url ? '<img class="memz-result-image" src="' + esc(mine.image_url) + '" alt="">' : "") +
      // Rule 4.4.5 (SPR-Z.10): throw this one back and get another, up to
      // three times a round. Gone once they're used up, and never shown
      // after submitting (the image is spent by then) or in Same Meme mode.
      (!already && r.image_swaps_left > 0
        ? '<button class="memz-btn memz-btn--ghost memz-btn--small" data-swap-image-btn>' +
          "תמונה אחרת (נשארו " + r.image_swaps_left + ")</button>"
        : "") +
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
          // SPR-W.5 (Rule 4.4.6): the way out of a blank box under a
          // clock. Below the send button, not above it -- someone who
          // already has an idea should not be offered one first.
          '<button type="button" class="memz-btn memz-btn--ghost memz-btn--small" data-ideas-btn>' +
          "תן לי רעיון 💡</button>" +
          '<ul class="memz-ideas" data-ideas hidden></ul>' +
          "</form>") +
      '<p class="memz-error" data-action-error></p>';
    countdown(root.querySelector("[data-timer]"), r.caption_deadline);
    var form = root.querySelector("[data-caption-form]");
    if (form && typedBefore) {
      // A swap rebuilt the screen; put back what they had already written.
      form.querySelector("[data-caption-input]").value = typedBefore;
    }
    var ideasBtn = root.querySelector("[data-ideas-btn]");
    if (ideasBtn) {
      ideasBtn.addEventListener("click", async function () {
        var list = root.querySelector("[data-ideas]");
        if (!list) return;
        ideasBtn.disabled = true;
        ideasBtn.textContent = "רגע...";
        try {
          var reply = await call("POST", "/rounds/" + r.number + "/ideas/");
          list.innerHTML = (reply.ideas || []).map(function (idea) {
            return '<li><button type="button" class="memz-idea" data-idea>' + esc(idea) + "</button></li>";
          }).join("");
          list.hidden = false;
          list.querySelectorAll("[data-idea]").forEach(function (chip) {
            chip.addEventListener("click", function () {
              // It goes *into* the box, it does not submit. The joke stays
              // the player's; this only gets them past the blank page.
              var input = root.querySelector("[data-caption-input]");
              if (!input) return;
              input.value = chip.textContent;
              input.focus();
              var end = input.value.length;
              input.setSelectionRange(end, end);
            });
          });
        } catch (e) {
          // Never an error on this screen: somebody stuck under a clock
          // asked for help and got a page telling them off. The button
          // simply goes away.
          list.hidden = true;
        }
        ideasBtn.textContent = "תן לי רעיון 💡";
        ideasBtn.disabled = false;
      });
    }
    var swapImageBtn = root.querySelector("[data-swap-image-btn]");
    if (swapImageBtn) {
      swapImageBtn.addEventListener("click", function () {
        guardedAction(function () { return call("POST", "/rounds/" + r.number + "/swap-image/"); }, swapImageBtn);
      });
    }
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

  // 2026-09-16 QA fix (Avi, live-testing the real game): this used to show
  // every meme in the round at once (a grid, just with a small staggered
  // fade-in) -- Avi wanted a real one-at-a-time slideshow instead, joke
  // after joke. The server already budgets `reveal_seconds_per_meme`
  // seconds per meme into `reveal_deadline` (game._start_reveal); working
  // backwards from that same deadline is what keeps every connected
  // screen -- different phones, different poll timings, the shared big
  // screen -- looking at the *same* meme at the *same* moment, without
  // needing a websocket or a separate "reveal started at" field.
  function revealIndexFor(r) {
    var count = (r.memes || []).length;
    if (count <= 0 || !r.reveal_deadline) return 0;
    var perMemeMs = (r.reveal_seconds_per_meme || 4) * 1000;
    var startedAt = new Date(r.reveal_deadline).getTime() - perMemeMs * count;
    var idx = Math.floor((serverNow() - startedAt) / perMemeMs);
    return Math.max(0, Math.min(count - 1, idx));
  }

  // SPR-Z.10: each meme's own slot ends here, not when the whole reveal
  // does. The countdown on this screen is the one that matters to a player
  // -- "how long do I still have to rate *this* one" -- so it counts to the
  // end of the current slot, not to the end of the round's whole reveal.
  function revealSlotDeadline(r, idx) {
    var count = (r.memes || []).length;
    if (count <= 0 || !r.reveal_deadline) return null;
    var perMemeMs = (r.reveal_seconds_per_meme || 10) * 1000;
    var startedAt = new Date(r.reveal_deadline).getTime() - perMemeMs * count;
    return new Date(startedAt + perMemeMs * (idx + 1)).toISOString();
  }

  function ratingAllowed(state) {
    // Relaxed has no scoring at all (spec §5.1) and Judge mode keeps its
    // own separate picking phase afterwards -- in both, the reveal stays
    // exactly the passive slideshow it was before SPR-Z.10.
    return state.game_mode !== "relaxed" && state.scoring_mode !== "judge";
  }

  var RATING_BUTTONS = [
    { key: "love", label: "אוהב 😍" },
    { key: "soso", label: "ככה ככה 😐" },
    { key: "meh", label: "פחות 🙈" },
  ];

  // SPR-W.1 (Rule 4.5.7): how the room took the meme, shown in the closing
  // beat of its slot. Counts only, never who -- a tally of verdicts
  // identifies nobody and was always the whole room's to see, which is
  // also why the TV gets it.
  var REACTION_FACES = { love: "😍", soso: "😐", meh: "🙈" };
  var springValue = null;   // the verdict just tapped, so the rebuilt button can spring too (Rule 4.5.6)

  function reactionLine(r, current) {
    if (!current || !r.reactions) return "";
    var counts = r.reactions[String(current.submission_id)];
    if (!counts) return "";
    var total = (counts.love || 0) + (counts.soso || 0) + (counts.meh || 0);
    if (!total) return '<p class="memz-reaction memz-reaction--quiet" data-reaction>עוד אף אחד לא הגיב...</p>';
    var parts = ["love", "soso", "meh"].filter(function (k) { return counts[k]; }).map(function (k) {
      return '<span class="memz-reaction-face">' + REACTION_FACES[k] + "</span>×" + counts[k];
    });
    return '<p class="memz-reaction" data-reaction>' + parts.join('<span class="memz-reaction-sep">·</span>') + "</p>";
  }

  function ratingBar(state, r, current) {
    // The TV never rates: it has no player behind it (spec §4.10), so it
    // shows the same slideshow with no controls at all.
    if (screenMode || !ratingAllowed(state) || !current) return "";
    if (current.is_mine) {
      // Rule 4.6.1: the author of the meme on screen cannot rate it, and
      // is told so in the one line Avi wrote himself.
      return '<p class="memz-lead memz-innocent" data-innocent-face>תעשה פרצוף תמים...</p>';
    }
    var values = r.rating_values || { love: 2, soso: 1, meh: 0 };
    var mine = (r.my_ratings || {})[String(current.submission_id)];
    var rated = mine !== undefined && mine !== null;
    // The spring survives the rebuild that follows a tap (Rule 4.5.6). On
    // a fast network the server answers inside the 320ms animation and
    // the screen is redrawn with the verdict recorded -- which would cut
    // the spring off halfway. So the button that comes back *chosen* is
    // sprung too, once, and the flag is cleared so a later poll never
    // replays it.
    var springNow = rated && mine === springValue;
    if (springNow) springValue = null;
    return (
      '<div class="memz-rating-bar" data-rating-bar>' +
      RATING_BUTTONS.map(function (b) {
        var value = values[b.key];
        var chosen = rated && mine === value;
        return (
          '<button class="memz-btn memz-rating-btn' + (chosen ? " memz-rating-btn--chosen" : "") +
          (chosen && springNow ? " memz-rating-btn--tapped" : "") +
          '"' + (rated ? " disabled" : "") + ' data-rate="' + value + '">' + b.label + "</button>"
        );
      }).join("") +
      "</div>" +
      (rated ? '<p class="memz-fineprint">נרשם. מחכים לבאה...</p>' : "")
    );
  }

  var revealedRenderKey = null;   // same idea as captioningRenderKey: don't replay the pop-in animation every poll tick for a meme that's already showing

  // SPR-W.1 (Rule 4.5.7): the reaction line is refreshed in place on each
  // poll, and gets its "beat" -- a larger, animated moment -- in the last
  // two seconds of the slot, once nearly everyone has tapped. Before that
  // it is a quiet running tally, so the counts never feel like a scoreboard
  // for the person whose meme it is.
  function updateReaction(r, current) {
    var el = root.querySelector("[data-reaction]");
    var fresh = reactionLine(r, current);
    if (!el || !fresh) return;
    var wrap = document.createElement("div");
    wrap.innerHTML = fresh;
    var next = wrap.firstChild;
    if (next.innerHTML !== el.innerHTML) {
      next.classList.toggle("memz-reaction--beat", el.classList.contains("memz-reaction--beat"));
      el.replaceWith(next);
    }
  }

  var reactionBeatTimer = null;

  function armReactionBeat(r, idx) {
    clearTimeout(reactionBeatTimer);
    var end = revealSlotDeadline(r, idx);
    if (!end) return;
    var msLeft = new Date(end).getTime() - serverNow();
    var beatAt = Math.max(0, msLeft - 2000);
    reactionBeatTimer = setTimeout(function () {
      var el = root.querySelector("[data-reaction]");
      if (el) el.classList.add("memz-reaction--beat");
    }, beatAt);
  }

  function renderRevealed(state) {
    var r = state.round;
    var count = (r.memes || []).length;
    var idx = revealIndexFor(r);
    var current = r.memes && r.memes[idx];
    var myRating = current ? (r.my_ratings || {})[String(current.submission_id)] : undefined;
    // The rating I've already given is part of the key: tapping a button
    // has to redraw this screen (the buttons lock, the chosen one fills
    // in), while a poll that changes nothing still must not. SPR-W.1: the
    // room's reaction to *this* meme is not in the key on purpose -- it
    // changes on nearly every poll while people tap, and a full rebuild
    // each time would replay the pop-in under a thumb mid-tap. It is
    // patched in place below instead (`updateReaction`).
    var key = state.code + ":" + r.number + ":" + idx + ":" + myRating;
    if (key === revealedRenderKey) {
      updateReaction(r, current);
      return;
    }
    var newMeme = revealedRenderKey === null || revealedRenderKey.indexOf(state.code + ":" + r.number + ":" + idx + ":") !== 0;
    revealedRenderKey = key;

    setScreen("game-revealed");
    var me = state.players.find(function (p) { return p.is_me; });
    var rating = ratingAllowed(state);
    root.innerHTML =
      '<h1 class="memz-title">' + (rating ? "מה דעתכם?" : "רגע של חשיפה...") + "</h1>" +
      '<p class="memz-fineprint">סבב ' + r.number + " מתוך " + state.round_count +
      (r.topic ? " · הנושא: " + esc(r.topic) : "") + "</p>" +
      '<div class="memz-timer" data-timer></div>' +
      (current
        ? '<img class="memz-result-image memz-reveal-image" src="' + esc(current.rendered_url) + '" alt="">' +
          (count > 1 ? '<p class="memz-fineprint" data-reveal-progress>' + (idx + 1) + " מתוך " + count + "</p>" : "")
        : "") +
      ratingBar(state, r, current) +
      reactionLine(r, current) +
      (missedThisRound(r) ? '<p class="memz-fineprint">לא הספקת, קורה. בסבב הבא!</p>' : "") +
      (me && me.is_host
        ? '<button class="memz-btn memz-btn--secondary memz-btn--wide" data-advance-btn>' +
          (state.scoring_mode === "judge" ? "למעבר להצבעה" : "לסיים את הסבב") + "</button>"
        : "") +
      '<p class="memz-error" data-action-error></p>';
    countdown(root.querySelector("[data-timer]"), revealSlotDeadline(r, idx) || r.reveal_deadline);
    var revealKey = state.code + ":" + r.number;
    if (revealedRoundSeen !== revealKey) {
      revealedRoundSeen = revealKey;
      window.memz.playSound("drumroll");
    } else if (newMeme) {
      // SPR-W.1 (F-W.1.3): every slot has a beginning you can hear across
      // the room, not only the round's first.
      window.memz.playSound("reveal");
    }
    armReactionBeat(r, idx);
    root.querySelectorAll("[data-rate]").forEach(function (rateBtn) {
      rateBtn.addEventListener("click", function () {
        // SPR-W.1 (Rule 4.5.6): the tap is felt before the network answers.
        // The verdict itself is still the server's to record; this is the
        // thumb's own confirmation, not the result.
        window.memz.vibrate(40);
        window.memz.playSound("pop");
        rateBtn.classList.add("memz-rating-btn--tapped");
        springValue = parseInt(rateBtn.dataset.rate, 10);
        guardedAction(function () {
          return call("POST", "/rounds/" + r.number + "/rate/", {
            submission_id: current.submission_id, value: parseInt(rateBtn.dataset.rate, 10),
          });
        }, rateBtn);
      });
    });
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }, btn); });
  }

  // 2026-09-16 QA fix (Avi, live-testing the real game): "בסוף שרואים את
  // כולם ובוחרים איזה הכי מצחיקה, זה עושה רפרש כל הזמן" -- voting polls
  // every second same as captioning, and this rebuilt the whole meme grid
  // on every single poll, replaying the tiles' own pop-in animation the
  // whole time you're looking at them and trying to decide. Nothing on
  // this screen actually needs the poll tick either, until the vote
  // itself is cast (which re-renders immediately from guardedAction's own
  // response, not waiting for the next poll) or the round moves on.
  var votingRenderKey = null;
  var screenVotingRenderKey = null;   // the shared big-screen's own voting render, tracked separately from the player-facing one above

  function renderVoting(state) {
    var r = state.round;
    var key = r.number + ":" + r.my_vote + ":" + missedThisRound(r);
    if (key === votingRenderKey) return;
    votingRenderKey = key;

    setScreen("game-voting");
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

  // (The per-meme vote count-up animation that used to live here went with
  // the per-meme scores themselves -- ACT-Z.14, see renderResult below.)

  // Same fix as renderVoting/renderCaptioning/renderRevealed above: once a
  // round's results are shown, nothing about them changes until the host
  // advances (score tallies are already final the moment `done` is
  // reached) -- so a full rebuild every poll only meant the tiles' pop-in
  // replaying over and over while everyone was just trying to read the
  // results.
  var resultRenderKey = null;

  function renderResult(state) {
    var r = state.round;
    if (r.number + "" === resultRenderKey) return;
    resultRenderKey = r.number + "";

    setScreen("game-result");
    var me = state.players.find(function (p) { return p.is_me; });
    var isLast = r.number >= state.round_count;
    var relaxed = state.game_mode === "relaxed";
    // Rule 4.7.2 (ACT-Z.14, Avi: "בסוף הראת גם את רשימת המובילים אבל גם
    // כמה כל מים קיבל. וזה עושה קשר"): showing each meme's points *next
    // to* a leaderboard rebuilt the link SPR-Z.10 removed -- a meme worth
    // 4 beside the one player whose score just rose by 4 names its author
    // as surely as a caption would. So a scoring round's result is the
    // table and nothing else. Relaxed mode, which has no scores at all and
    // therefore nothing to correlate, still shows the memes: seeing them
    // together is the whole point of that mode (spec §5.1).
    root.innerHTML =
      '<h1 class="memz-title">' + (relaxed ? "היה כיף!" : "תוצאות הסבב") + "</h1>" +
      (relaxed
        ? '<div class="memz-meme-grid">' + r.results.map(function (row, i) {
            return (
              '<figure class="memz-meme-tile' + (row.is_mine ? " memz-meme-tile--mine" : "") +
              '" style="animation-delay:' + (i * 90) + 'ms">' +
              '<img src="' + esc(row.rendered_url) + '" alt="">' +
              (row.is_mine ? "<figcaption>שלכם</figcaption>" : "") +
              "</figure>"
            );
          }).join("") + "</div>"
        : '<h2 class="memz-field-label">טבלת מובילים</h2>' +
          '<ul class="memz-player-list">' + rankedPlayerRows(state.players) + "</ul>") +
      (me && me.is_host
        ? '<button class="memz-btn memz-btn--primary memz-btn--wide" data-advance-btn>' + (isLast ? "לתוצאות הסופיות" : "לסבב הבא") + "</button>"
        : "") +
      // SPR-W.5 (Rule 4.7.3): the wait is finite and says so. "מחכים
      // למארח/ת" with no end to it was the one screen in the game that
      // could sit there forever, and the host who put their phone down is
      // exactly the person who cannot see that it has.
      (r.result_deadline
        ? '<p class="memz-lead">' + (isLast ? "לתוצאות הסופיות בעוד " : "לסבב הבא בעוד ") +
          '<b data-result-timer></b></p>'
        : me && me.is_host ? "" : '<p class="memz-lead">מחכים למארח/ת...</p>');
    var autoTimer = root.querySelector("[data-result-timer]");
    if (autoTimer) countdown(autoTimer, r.result_deadline);
    var btn = root.querySelector("[data-advance-btn]");
    if (btn) btn.addEventListener("click", function () { guardedAction(function () { return call("POST", "/advance/"); }, btn); });
  }

  // SPR-W.5: the round-result leaderboard used to reuse `playerRow`, which
  // opens with a presence dot -- so the top row showed a coloured circle
  // beside the leading name and read as a gold medal, with the second
  // place's yellow "away" dot reading as silver. Presence still matters
  // mid-game ("has someone gone?"), so it is not dropped, it is demoted:
  // the position gets the number that actually means position, and only a
  // player who is *not* active carries a marker at all.
  function rankRow(p, index, move) {
    var away = p.is_ai
      ? '<span class="memz-rank-flag" title="בוט">🤖</span>'
      : p.presence === "active"
      ? ""
      : '<span class="memz-rank-flag" title="לא בקשר כרגע">⏳</span>';
    return (
      '<li class="memz-player-row' + (p.is_me ? " memz-player-row--me" : "") + '">' +
      '<span class="memz-rank-n">' + (index + 1) + "</span>" +
      "<span>" + esc(p.nickname) + (p.is_host ? " 👑" : "") + away + "</span>" +
      '<span class="memz-player-score">' + p.score + move + "</span>" +
      "</li>"
    );
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
      return rankRow(p, i, move);
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

  // SPR-W.3: the two cards the evening ends with. Server-rendered JPEGs at
  // a stable address (see memz/share_cards.py), shown on the podium and
  // shareable in one tap each.
  function cardUrl(code, kind) {
    return "/memz/s/" + encodeURIComponent(code) + "/card/" + kind + ".jpg";
  }

  function shareCardsBlock(state) {
    if (screenMode) return "";
    var cards = [
      // The meme card is listed first and only when the game actually has
      // one: `has_meme_card` comes from the server rather than being
      // guessed, because a game nobody submitted to has no best meme and a
      // broken <img> at the podium is worse than one card.
      state.has_meme_card
        ? { kind: "meme", label: "המם של הערב", alt: "המם של הערב" }
        : null,
      { kind: "podium", label: "טבלת המנצחים", alt: "טבלת המנצחים" },
    ].filter(Boolean);
    return (
      '<div class="memz-cards">' +
      cards.map(function (c) {
        var url = cardUrl(state.code, c.kind);
        return (
          '<figure class="memz-card-share">' +
          '<img src="' + esc(url) + '" alt="' + esc(c.alt) + '" loading="lazy">' +
          '<button type="button" class="memz-btn memz-btn--secondary memz-btn--wide" ' +
          'data-share-card="' + c.kind + '">שיתוף ' + esc(c.label) + " 💬</button>" +
          "</figure>"
        );
      }).join("") +
      "</div>"
    );
  }

  async function shareCard(state, kind, btn) {
    var url = window.location.origin + cardUrl(state.code, kind);
    var text = kind === "meme" ? "המם של הערב שלנו ב-memz 😂" : "ככה נגמר המשחק שלנו ב-memz 🏆";
    // The good path: hand WhatsApp the actual picture, so it arrives as a
    // photo in the thread rather than a link somebody has to tap. Only
    // some browsers can share files, and a browser that says it can still
    // refuses some types, so `canShare` is asked about this exact file.
    try {
      if (navigator.canShare && navigator.share) {
        var blob = await (await fetch(url)).blob();
        var file = new File([blob], "memz-" + kind + ".jpg", { type: "image/jpeg" });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], text: text });
          return;
        }
      }
    } catch (err) {
      if (err && err.name === "AbortError") return;   // they changed their mind, not a failure
    }
    // The fallback: wa.me with the card's own address. WhatsApp renders a
    // preview of a direct image URL, so this still arrives as a picture --
    // one tap further away, and it works everywhere, including inside an
    // installed PWA (the ACT-Z.15 lesson).
    window.location.href = "https://wa.me/?text=" + encodeURIComponent(text + "\n" + url);
  }

  function renderFinished(state) {
    setScreen("game-finished");
    if (finishedCelebrated !== state.code) {
      finishedCelebrated = state.code;
      spawnConfetti();
      window.memz.playSound("fanfare");   // SPR-W.1 (F-W.1.3): the podium is an event, once
    }
    var me = state.players.find(function (p) { return p.is_me; });
    var podium = state.podium || [];
    root.innerHTML =
      '<h1 class="memz-title">🎉 נגמר!</h1>' +
      shareCardsBlock(state) +
      '<ol class="memz-podium">' + podium.map(function (row, i) {
        return '<li><span class="memz-podium-place">' + (i + 1) + "</span>" +
          '<span class="memz-podium-who">' + esc(row.nickname) +
          (row.tied_with_next ? " (תיקו)" : "") +
          // SPR-W.5: the badge, and under it what it means. The review's
          // own finding: a title is a reward only if the person can tell
          // what they did to earn it.
          (row.title
            ? '<span class="memz-title-badge">' + esc(row.title) + "</span>" +
              (row.title_note ? '<span class="memz-title-note">' + esc(row.title_note) + "</span>" : "")
            : "") + "</span>" +
          '<span class="memz-podium-score">' + row.score + "</span></li>";
      }).join("") + "</ol>" +
      '<h2 class="memz-field-label">כל הממים</h2>' +
      '<div class="memz-meme-grid">' + (state.gallery || []).map(function (g) {
        return (
          // Rule 4.7.1 (SPR-Z.10): the end-of-game gallery is anonymous
          // too -- it used to name every meme's author, which would hand
          // back at the podium exactly what the round result stopped
          // revealing. Only your own is marked, and only to you.
          '<figure class="memz-meme-tile' + (g.is_mine ? " memz-meme-tile--mine" : "") +
          '"><img src="' + esc(g.rendered_url) + '" alt="">' +
          (g.is_mine ? "<figcaption>שלכם</figcaption>" : "") +
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

    root.querySelectorAll("[data-share-card]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        shareCard(state, btn.dataset.shareCard, btn);
      });
    });

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

  // ------------------------------------------------ SPR-W.4: the TV show
  //
  // Until now the big screen ran the phone's own renderers at a bigger
  // font. That is a page, and a page seen from four metres away across a
  // room is unreadable and, worse, undramatic: the meme sat in a column
  // with a heading above it and fineprint below, taking a third of the
  // wall. The phone is the controller; this is the show. So the TV gets
  // its own renderers -- the meme fills the screen, the room's verdicts
  // land on it live, and the standings physically move.

  function tvPill(text, cls) {
    return '<span class="memz-tv-pill' + (cls ? " " + cls : "") + '">' + esc(text) + "</span>";
  }

  function tvReactionStrip(r, current) {
    // The same counts the phones see (SPR-W.1, Rule 4.5.7), but this is
    // where they belong: everybody is already looking at the wall, and a
    // number that grows while the room taps is the shared moment the
    // phones can only hint at. Counts only -- never who.
    if (!current || !r.reactions) return "";
    var counts = r.reactions[String(current.submission_id)] || {};
    return (
      '<div class="memz-tv-reactions" data-tv-reactions>' +
      ["love", "soso", "meh"].map(function (k) {
        return (
          '<div class="memz-tv-reaction' + (counts[k] ? " is-live" : "") + '">' +
          '<span class="memz-tv-face">' + REACTION_FACES[k] + "</span>" +
          '<b data-tv-count="' + k + '">' + (counts[k] || 0) + "</b></div>"
        );
      }).join("") +
      "</div>"
    );
  }

  function updateTvReactions(r, current) {
    // Patched in place, never rebuilt: these change on nearly every poll
    // while the room taps, and replacing the markup would restart the
    // count's own bump animation on numbers that did not move.
    if (!current || !r.reactions) return;
    var counts = r.reactions[String(current.submission_id)] || {};
    ["love", "soso", "meh"].forEach(function (k) {
      var el = root.querySelector('[data-tv-count="' + k + '"]');
      if (!el) return;
      var next = String(counts[k] || 0);
      if (el.textContent === next) return;
      el.textContent = next;
      el.parentElement.classList.add("is-live");
      el.classList.remove("memz-tv-count--bump");
      void el.offsetWidth;   // restart the animation rather than let it be ignored
      el.classList.add("memz-tv-count--bump");
    });
  }

  var tvRenderKey = null;

  function renderTvLobby(state) {
    setScreen("game-lobby");
    var key = "lobby:" + state.players.map(function (p) { return p.id; }).join(",");
    if (key === tvRenderKey) return;
    tvRenderKey = key;
    root.innerHTML =
      '<div class="memz-tv memz-tv--lobby">' +
      '<div class="memz-tv-joinbox">' +
      '<p class="memz-tv-kicker">להצטרף במשחק</p>' +
      '<h1 class="memz-tv-code">' + esc(state.code) + "</h1>" +
      '<img class="memz-tv-qr" src="/memz/s/' + encodeURIComponent(state.code) + '/qr.png" alt="">' +
      '<p class="memz-tv-kicker">babook.co.il/memz</p>' +
      "</div>" +
      '<ul class="memz-tv-players">' + state.players.map(function (p) {
        return '<li class="memz-tv-player">' + esc(p.nickname) + (p.is_host ? " 👑" : "") + "</li>";
      }).join("") + "</ul>" +
      "</div>";
  }

  function renderTvCaptioning(state) {
    var r = state.round;
    setScreen("game-lobby");
    var key = "cap:" + r.number + ":" + r.submitted_count;
    if (key === tvRenderKey) return;
    var fresh = tvRenderKey === null || tvRenderKey.indexOf("cap:" + r.number + ":") !== 0;
    tvRenderKey = key;
    var done = r.submitted_count, total = r.total_count || 1;
    if (fresh) {
      root.innerHTML =
        '<div class="memz-tv memz-tv--waiting">' +
        '<p class="memz-tv-kicker">סבב ' + r.number + " מתוך " + state.round_count + "</p>" +
        '<h1 class="memz-tv-headline">כותבים...</h1>' +
        '<div class="memz-tv-progress"><span data-tv-bar></span></div>' +
        '<p class="memz-tv-big" data-tv-submitted></p>' +
        '<p class="memz-tv-timer" data-timer></p>' +
        "</div>";
      countdown(root.querySelector("[data-timer]"), r.caption_deadline);
    }
    // Only the number and the bar move between polls; rebuilding the
    // block would restart the countdown's interval every second.
    var bar = root.querySelector("[data-tv-bar]");
    if (bar) bar.style.width = Math.round((done / total) * 100) + "%";
    var sub = root.querySelector("[data-tv-submitted]");
    if (sub) sub.textContent = done + " מתוך " + total + " כבר שלחו";
  }

  function renderTvReveal(state) {
    var r = state.round;
    var count = (r.memes || []).length;
    var idx = revealIndexFor(r);
    var current = r.memes && r.memes[idx];
    setScreen("game-revealed");
    var key = "reveal:" + r.number + ":" + idx;
    if (key === tvRenderKey) {
      updateTvReactions(r, current);
      return;
    }
    var newSlot = tvRenderKey !== null && tvRenderKey.indexOf("reveal:" + r.number + ":") === 0;
    tvRenderKey = key;

    root.innerHTML =
      '<div class="memz-tv memz-tv--reveal">' +
      '<div class="memz-tv-stage">' +
      (current ? '<img class="memz-tv-meme" src="' + esc(current.rendered_url) + '" alt="">' : "") +
      "</div>" +
      '<div class="memz-tv-rail">' +
      '<h1 class="memz-tv-kicker">סבב ' + r.number + " מתוך " + state.round_count +
      (count > 1 ? " · מם " + (idx + 1) + " מתוך " + count : "") + "</h1>" +
      '<p class="memz-tv-timer" data-timer></p>' +
      tvReactionStrip(r, current) +
      '<p class="memz-tv-hint">מצביעים בטלפון</p>' +
      "</div></div>";
    countdown(root.querySelector("[data-timer]"), revealSlotDeadline(r, idx) || r.reveal_deadline);
    if (newSlot) window.memz.playSound("reveal");
    else window.memz.playSound("drumroll");
  }

  // The standings, moved rather than redrawn. Rows are keyed by player id
  // and animated with FLIP (measure where each row is, rebuild, measure
  // again, play the difference backwards): the point of a leaderboard on a
  // wall is watching somebody overtake somebody, which a list that simply
  // appears in a new order never shows.
  function tvStandingsRows(state) {
    var players = state.players.slice().sort(function (a, b) { return b.score - a.score; });
    return players.map(function (p, i) {
      return (
        '<li class="memz-tv-rank' + (i === 0 ? " is-leader" : "") + '" data-rank-id="' + p.id + '">' +
        '<span class="memz-tv-rank-n">' + (i + 1) + "</span>" +
        '<span class="memz-tv-rank-name">' + esc(p.nickname) + "</span>" +
        '<span class="memz-tv-rank-score">' + p.score + "</span></li>"
      );
    }).join("");
  }

  function flipStandings(listEl, redraw) {
    var before = {};
    listEl.querySelectorAll("[data-rank-id]").forEach(function (row) {
      before[row.dataset.rankId] = row.getBoundingClientRect().top;
    });
    redraw();
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    listEl.querySelectorAll("[data-rank-id]").forEach(function (row) {
      var was = before[row.dataset.rankId];
      if (was === undefined) return;
      var delta = was - row.getBoundingClientRect().top;
      if (!delta) return;
      row.style.transform = "translateY(" + delta + "px)";
      row.style.transition = "none";
      requestAnimationFrame(function () {
        row.style.transition = "transform 520ms cubic-bezier(.2,.8,.2,1)";
        row.style.transform = "";
      });
    });
  }

  function renderTvResult(state) {
    var r = state.round;
    setScreen("game-result");
    var scoreKey = "result:" + r.number + ":" + state.players.map(function (p) { return p.score; }).join(",");
    if (scoreKey === tvRenderKey) return;
    var sameRound = tvRenderKey !== null && tvRenderKey.indexOf("result:" + r.number + ":") === 0;
    tvRenderKey = scoreKey;

    if (!sameRound) {
      root.innerHTML =
        '<div class="memz-tv memz-tv--result">' +
        '<p class="memz-tv-kicker">סוף סבב ' + r.number + " מתוך " + state.round_count + "</p>" +
        '<h1 class="memz-tv-headline">הטבלה</h1>' +
        '<ol class="memz-tv-ranks" data-tv-ranks>' + tvStandingsRows(state) + "</ol>" +
        // SPR-W.5: the wall says how long this pause lasts, so the room
        // knows to keep looking at it.
        (r.result_deadline ? '<p class="memz-tv-timer" data-timer></p>' : "") +
        "</div>";
      var tvResultTimer = root.querySelector("[data-timer]");
      if (tvResultTimer) countdown(tvResultTimer, r.result_deadline);
      return;
    }
    var list = root.querySelector("[data-tv-ranks]");
    if (!list) return;
    flipStandings(list, function () { list.innerHTML = tvStandingsRows(state); });
  }

  function renderTvFinished(state) {
    setScreen("game-finished");
    var key = "finished:" + state.code;
    if (key === tvRenderKey) return;
    tvRenderKey = key;
    spawnConfetti();
    window.memz.playSound("fanfare");
    var podium = state.podium || [];
    root.innerHTML =
      '<div class="memz-tv memz-tv--finished">' +
      '<h1 class="memz-tv-headline">🎉 נגמר!</h1>' +
      '<ol class="memz-tv-ranks">' + podium.map(function (row, i) {
        return (
          '<li class="memz-tv-rank' + (i === 0 ? " is-leader" : "") + '">' +
          '<span class="memz-tv-rank-n">' + (i + 1) + "</span>" +
          '<span class="memz-tv-rank-name">' + esc(row.nickname) +
          (row.title
            ? '<b class="memz-tv-rank-title">' + esc(row.title) +
              (row.title_note ? " · " + esc(row.title_note) : "") + "</b>"
            : "") + "</span>" +
          '<span class="memz-tv-rank-score">' + row.score + "</span></li>"
        );
      }).join("") + "</ol>" +
      // SPR-W.3's cards, on the wall: the room can see what is worth
      // forwarding, and anyone photographing the TV gets the good version
      // of the picture rather than a leaderboard.
      (state.has_meme_card
        ? '<img class="memz-tv-card" src="' + esc(cardUrl(state.code, "meme")) + '" alt="">'
        : "") +
      '<p class="memz-tv-kicker">babook.co.il/memz</p>' +
      "</div>";
  }

  function renderScreenMode(state) {
    // The TV/laptop view: read-only, its own layout (SPR-W.4).
    if (state.status === "lobby") return renderTvLobby(state);
    // SPR-W.2: the booth's clock and count on the wall is exactly what a
    // room full of people pointing phones at each other wants. Its own
    // renderer already guards the camera off the TV (no player, no token).
    if (state.status === "booth") return renderBooth(state);
    var r = state.round;
    if (!r) return;
    if (r.status === "captioning") {
      renderTvCaptioning(state);
    } else if (r.status === "revealed") {
      renderTvReveal(state);
    } else if (r.status === "voting") {
      // Judge mode's own phase, which only exists there now. Nothing on
      // it changes while the judge decides, so it is built once.
      var screenVoteKey = "screen:" + r.number;
      if (screenVoteKey !== screenVotingRenderKey) {
        screenVotingRenderKey = screenVoteKey;
        setScreen("game-voting");
        root.innerHTML =
          '<div class="memz-tv memz-tv--waiting">' +
          '<p class="memz-tv-kicker">סבב ' + r.number + " מתוך " + state.round_count +
          " · " + state.players.length + " שחקנים בחדר</p>" +
          '<h1 class="memz-tv-headline">' +
          (r.judge ? esc(r.judge.nickname) + " מחליט/ה..." : "מצביעים...") + "</h1>" +
          '<p class="memz-tv-hint">כל הממים של הסבב, והשופט/ת בוחר/ת אחד</p>' +
          '<div class="memz-tv-grid">' +
          r.memes.map(function (m) { return '<img src="' + esc(m.rendered_url) + '" alt="">'; }).join("") +
          "</div></div>";
      }
    } else {
      renderTvResult(state);
    }
  }

  function render(state) {
    updateServerClockOffset(state);   // every state update, poll-driven or from an action's own response
    if (screenMode) {
      if (state.status === "finished") renderTvFinished(state);
      else renderScreenMode(state);
      schedulePoll(state);
      return;
    }

    if (state.status === "finished" && state.next_session) {
      window.memz.setPlayerToken(state.next_session.code, state.next_session.token);
      window.location.href = "/memz/s/" + state.next_session.code + "/";
      return;
    }

    if (state.status !== "lobby") showLobbyUploader(false);
    if (state.status !== "booth") showBoothUploader(false);
    if (state.status === "lobby") renderLobby(state);
    else if (state.status === "booth") renderBooth(state);
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
    var ms = { lobby: 2000, booth: 1000, captioning: 1000, revealed: 1000, voting: 1000, done: 2000, finished: 5000 };
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
