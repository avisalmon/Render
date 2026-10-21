/* The strategy lab's screen (REQ-B.11). Reads the form, hands the work to a
   worker, draws what comes back, and saves a small summary if asked.

   Nothing about the hands is sent to the server: the server is told the
   conditions and the summary, and checks the shape of both. */

(function () {
  "use strict";

  var root = document.getElementById("bjLab");
  if (!root) return;

  var boot = JSON.parse(document.getElementById("bjLabBoot").textContent);
  var Charts = window.LabCharts;
  var fmt = Charts.fmt;

  function $(id) { return document.getElementById(id); }

  // A freeze step is [profit that sets it off, amount sent home]. Runs saved
  // before that was so hold a bare number, which meant both at once.
  function pairs(list) {
    return list.map(function (e) { return Array.isArray(e) ? [e[0], e[1]] : [e, e]; });
  }

  var state = {
    ladder: boot.settings.policy.ladder.slice(),
    freeze: pairs(boot.settings.policy.freeze),
    overrides: Object.assign({}, boot.settings.overrides || {}),
    worker: null,
    result: null
  };

  /* ---------- the form ---------- */

  function randomSeed() { return Math.floor(Math.random() * 4294967295); }

  function mode() {
    return document.querySelector('input[name="mode"]:checked').value;
  }

  function fill() {
    var r = boot.rules, p = boot.settings.policy, s = boot.settings;
    $("labDecks").value = r.decks;
    $("labPays").value = r.blackjack_pays;
    $("labSplits").value = r.max_splits;
    $("labH17").checked = !!r.dealer_hits_soft_17;
    $("labDas").checked = !!r.double_after_split;
    $("labResplitAces").checked = !!r.resplit_aces;
    $("labHitSplitAces").checked = !!r.hit_split_aces;
    $("labMinBet").value = p.minBet;
    $("labLimit").value = p.limit;
    $("labStart").value = p.start;
    $("labAfterWin").value = p.afterWin;
    $("labAtLimit").value = p.atLimit;
    $("labShort").value = p.short;
    $("labFreezeAfter").value = p.freezeAfter;
    $("labHands").value = s.handsPerDay;
    $("labDays").value = s.days || 30;
    $("labGoal").value = s.goal || "ahead";
    $("labSearchDays").value = Math.min(s.days || 40, 60);
    $("labHoldout").value = s.holdoutDays || 100;
    $("labBudget").value = 20;
    $("labSeed").value = s.seed != null ? s.seed : randomSeed();
    document.querySelector('input[name="mode"][value="' + boot.mode + '"]').checked = true;
    document.querySelector('input[name="chart"][value="' + (s.chart || "classic") + '"]').checked = true;
    var mix = s.mix || { ahead: 5, avg: 3, survive: 2 };
    $("labMixAhead").value = mix.ahead;
    $("labMixAvg").value = mix.avg;
    $("labMixSurvive").value = mix.survive;
    showMode();
    renderLadder();
    renderFreeze();
    fillOverridePlayers();
    renderOverrides();
  }

  function showMode() {
    var m = mode();
    Array.prototype.forEach.call(root.querySelectorAll("[data-for]"), function (el) {
      el.hidden = el.getAttribute("data-for") !== m;
    });
    $("labMixBox").hidden = !(m === "search" && $("labGoal").value === "mix");
  }
  $("labGoal").addEventListener("change", showMode);

  function numberRows(containerId, list, noun, minRows) {
    var box = $(containerId);
    box.textContent = "";
    list.forEach(function (value, i) {
      var row = document.createElement("div");
      row.className = "bj-lab-row";
      var label = document.createElement("span");
      label.className = "bj-muted bj-small";
      label.textContent = noun + " " + (i + 1);
      var input = document.createElement("input");
      input.type = "number"; input.min = "1"; input.step = "1"; input.value = value;
      input.setAttribute("inputmode", "numeric");
      input.setAttribute("aria-label", noun + " " + (i + 1));
      input.addEventListener("input", function () { list[i] = parseInt(input.value, 10) || 0; });
      var remove = document.createElement("button");
      remove.type = "button"; remove.className = "bj-btn bj-btn-small bj-btn-quiet";
      remove.textContent = "הסרה";
      remove.setAttribute("aria-label", "הסרת " + noun + " " + (i + 1));
      remove.disabled = list.length <= minRows;
      remove.addEventListener("click", function () {
        list.splice(i, 1);
        numberRows(containerId, list, noun, minRows);
      });
      row.appendChild(label); row.appendChild(input); row.appendChild(remove);
      box.appendChild(row);
    });
  }

  function renderLadder() { numberRows("labLadder", state.ladder, "שלב", 1); }
  function renderFreeze() {
    var box = $("labFreeze");
    box.textContent = "";
    state.freeze.forEach(function (step, i) {
      var row = document.createElement("div");
      row.className = "bj-lab-row bj-lab-row-pair";
      var label = document.createElement("span");
      label.className = "bj-muted bj-small";
      label.textContent = "שלב " + (i + 1);
      row.appendChild(label);
      [["כשהרווח מגיע ל", 0], ["מוציאים הביתה", 1]].forEach(function (part) {
        var wrap = document.createElement("label");
        wrap.className = "bj-lab-mini";
        var text = document.createElement("span");
        text.className = "bj-muted bj-small";
        text.textContent = part[0];
        var input = document.createElement("input");
        input.type = "number"; input.min = "1"; input.step = "1"; input.value = step[part[1]];
        input.setAttribute("inputmode", "numeric");
        input.setAttribute("aria-label", "שלב " + (i + 1) + ": " + part[0]);
        input.addEventListener("input", function () { step[part[1]] = parseInt(input.value, 10) || 0; });
        wrap.appendChild(text); wrap.appendChild(input);
        row.appendChild(wrap);
      });
      var remove = document.createElement("button");
      remove.type = "button"; remove.className = "bj-btn bj-btn-small bj-btn-quiet";
      remove.textContent = "הסרה";
      remove.setAttribute("aria-label", "הסרת שלב " + (i + 1));
      remove.addEventListener("click", function () { state.freeze.splice(i, 1); renderFreeze(); });
      row.appendChild(remove);
      box.appendChild(row);
    });
  }

  $("labLadderAdd").addEventListener("click", function () {
    if (state.ladder.length >= boot.limits.maxLadder) return;
    var last = state.ladder[state.ladder.length - 1] || 15;
    state.ladder.push(last * 3);
    renderLadder();
  });
  $("labFreezeAdd").addEventListener("click", function () {
    if (state.freeze.length >= boot.limits.maxFreeze) return;
    var last = state.freeze[state.freeze.length - 1];
    state.freeze.push(last ? last.slice() : [500, 500]);
    renderFreeze();
  });

  Array.prototype.forEach.call(document.querySelectorAll('input[name="mode"]'), function (el) {
    el.addEventListener("change", showMode);
  });
  $("labReseed").addEventListener("click", function () { $("labSeed").value = randomSeed(); });

  /* ---------- changes to the table ---------- */

  var KIND = { hard: "יד קשה", soft: "יד רכה", pair: "זוג" };
  var ACTION = { H: "קלף", S: "עצור", D: "הכפל", P: "פצל" };

  function playerLabel(kind, n) {
    if (kind === "soft") return "אס ו-" + (n - 11);
    if (kind === "pair") return n === 11 ? "אסים" : String(n);
    return String(n);
  }
  function dealerLabel(d) { return d === 11 ? "אס" : String(d); }

  function fillOverridePlayers() {
    var kind = $("labOvKind").value;
    var ranges = { hard: [5, 20], soft: [13, 20], pair: [2, 11] };
    var sel = $("labOvPlayer");
    sel.textContent = "";
    for (var n = ranges[kind][0]; n <= ranges[kind][1]; n++) {
      var o = document.createElement("option");
      o.value = n; o.textContent = playerLabel(kind, n);
      sel.appendChild(o);
    }
    if (kind === "pair") sel.value = 8;
    if (kind === "hard") sel.value = 16;
    if (kind === "soft") sel.value = 18;
  }

  function fillDealer() {
    var sel = $("labOvDealer");
    sel.textContent = "";
    var all = document.createElement("option");
    all.value = "*"; all.textContent = "מול כל קלף של הדילר";
    sel.appendChild(all);
    for (var d = 2; d <= 11; d++) {
      var o = document.createElement("option");
      o.value = d; o.textContent = "מול " + dealerLabel(d);
      sel.appendChild(o);
    }
  }
  fillDealer();

  $("labOvKind").addEventListener("change", fillOverridePlayers);
  $("labOvAdd").addEventListener("click", function () {
    var kind = $("labOvKind").value, player = $("labOvPlayer").value;
    var dealer = $("labOvDealer").value, action = $("labOvAction").value;
    var dealers = dealer === "*" ? [2, 3, 4, 5, 6, 7, 8, 9, 10, 11] : [parseInt(dealer, 10)];
    dealers.forEach(function (d) { state.overrides[kind + "|" + player + "|" + d] = action; });
    renderOverrides();
  });

  function renderOverrides() {
    var box = $("labOverrides");
    box.textContent = "";
    var groups = {};
    Object.keys(state.overrides).forEach(function (key) {
      var p = key.split("|");
      var g = p[0] + "|" + p[1] + "|" + state.overrides[key];
      (groups[g] = groups[g] || []).push(parseInt(p[2], 10));
    });
    var names = Object.keys(groups);
    if (!names.length) {
      var none = document.createElement("li");
      none.className = "bj-muted bj-small";
      none.textContent = "אין שינויים. הריצה משחקת בדיוק לפי הטבלה הקלאסית.";
      box.appendChild(none);
      return;
    }
    names.forEach(function (g) {
      var p = g.split("|"), dealers = groups[g].sort(function (a, b) { return a - b; });
      var li = document.createElement("li");
      li.className = "bj-lab-chip";
      var against = dealers.length === 10 ? "מול הכול" : "מול " + dealers.map(dealerLabel).join(", ");
      li.appendChild(document.createTextNode(KIND[p[0]] + " " + playerLabel(p[0], parseInt(p[1], 10)) + " " + against + ": " + ACTION[p[2]] + " "));
      var remove = document.createElement("button");
      remove.type = "button"; remove.className = "bj-lab-chip-x";
      remove.textContent = "הסרה";
      remove.addEventListener("click", function () {
        dealers.forEach(function (d) { delete state.overrides[p[0] + "|" + p[1] + "|" + d]; });
        renderOverrides();
      });
      li.appendChild(remove);
      box.appendChild(li);
    });
  }


  /* ---------- the recommender (REQ-B.11.29) ---------- */

  var model = null;

  function adviceNote(text, warn) {
    var el = $("labAdviceNote");
    el.textContent = text;
    el.hidden = !text;
    el.classList.toggle("bj-lab-advice-warn", !!warn);
  }

  function conditions() {
    var big = 1000000000;
    return {
      start: whole("labStart", 1, big, "כסף להתחלה"),
      minBet: whole("labMinBet", 1, big, "הימור מינימלי"),
      limit: whole("labLimit", 1, big, "מגבלת שולחן"),
      handsPerDay: whole("labHands", 1, boot.limits.maxHands, "ידיים ביום"),
      decks: parseInt($("labDecks").value, 10),
      h17: $("labH17").checked,
      das: $("labDas").checked,
      pays: $("labPays").value
    };
  }

  function applyAdvice() {
    var c;
    try { c = conditions(); } catch (err) { adviceNote(err.message, true); return; }
    if (c.limit < c.minBet) { adviceNote("מגבלת השולחן קטנה מההימור המינימלי.", true); return; }
    var out = window.LabRecommend.recommend(model, c);
    if (out.outside.length) {
      var r = model.ranges, why = [];
      if (out.outside.indexOf("hands") >= 0) why.push("ידיים ביום בין " + fmt(r.handsPerDay[0]) + " ל-" + fmt(r.handsPerDay[1]));
      if (out.outside.indexOf("start") >= 0) why.push("כסף להתחלה בין " + fmt(r.start[0]) + " ל-" + fmt(r.start[1]) + ", ולפחות 5 הימורים מינימליים");
      if (out.outside.indexOf("limit") >= 0) why.push("מגבלת שולחן בין " + r.limitRatio[0] + " ל-" + r.limitRatio[1] + " הימורים מינימליים");
      if (out.outside.indexOf("decks") >= 0) why.push(r.decks.join(", ") + " חפיסות");
      adviceNote("המודל לא אומן על שולחן כזה, ולכן הוא לא ממליץ כאן. הוא למד: " + why.join("; ") + ". הטופס לא שונה.", true);
      return;
    }
    var p = out.policy;
    state.ladder = p.ladder.slice();
    state.freeze = p.freeze.map(function (e) { return e.slice(); });
    $("labAfterWin").value = p.afterWin;
    $("labAtLimit").value = p.atLimit;
    $("labShort").value = p.short;
    $("labFreezeAfter").value = p.freezeAfter;
    renderLadder();
    renderFreeze();
    var m = model.measured;
    var long = c.handsPerDay > 800 && m.ahead_pct_long != null;
    var mine = m.ahead_pct_short != null ? (long ? m.ahead_pct_long : m.ahead_pct_short) : m.ahead_pct;
    var theirs = m.default_ahead_pct_short != null ? (long ? m.default_ahead_pct_long : m.default_ahead_pct_short) : m.default_ahead_pct;
    var text = "מולא: " + Charts.policyLine(p) + (p.freezeAfter === "repeat" ? ", ואחרי השלב האחרון ממשיכים לפיו" : "") + ". " +
      "על שולחנות שהמודל לא ראה, עם ימים " + (long ? "ארוכים (יותר מ-800 ידיים)" : "של עד 800 ידיים") +
      ", המלצות כאלה הסתיימו ברווח ב-" + mine + "% מהימים, מול " + theirs + "% במדיניות ברירת המחדל. " +
      (mine < 50 ? "יותר מחצי מהימים עדיין מפסידים" : "עדיין הרבה ימים מפסידים") +
      ": היתרון של הקזינו נשאר, והממוצע לא משתנה.";
    var warn = [];
    if (document.querySelector('input[name="chart"]:checked').value !== "classic") warn.push("המודל אומן על הטבלה הקלאסית.");
    if (Object.keys(state.overrides).length) warn.push("המודל אומן בלי שינויים בטבלה.");
    adviceNote(text + (warn.length ? " " + warn.join(" ") : ""), warn.length > 0);
  }

  $("labRecommend").addEventListener("click", function () {
    if (model) { applyAdvice(); return; }
    adviceNote("טוען את המודל...", false);
    fetch(root.dataset.model, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (m) { model = m; applyAdvice(); })
      .catch(function () { adviceNote("לא הצלחתי לטעון את המודל. נסו שוב.", true); });
  });

  /* ---------- reading the form ---------- */

  function whole(id, low, high, what) {
    var v = Number($(id).value);
    if (!Number.isInteger(v) || v < low || v > high) {
      throw new Error(what + ": מספר שלם בין " + fmt(low) + " ל-" + fmt(high) + ".");
    }
    return v;
  }

  function rulesFromForm() {
    return {
      decks: parseInt($("labDecks").value, 10),
      blackjack_pays: $("labPays").value,
      max_splits: parseInt($("labSplits").value, 10),
      dealer_hits_soft_17: $("labH17").checked,
      double_after_split: $("labDas").checked,
      resplit_aces: $("labResplitAces").checked,
      hit_split_aces: $("labHitSplitAces").checked
    };
  }

  function readForm() {
    var big = 1000000000;
    var policy = {
      start: whole("labStart", 1, big, "כסף להתחלה"),
      minBet: whole("labMinBet", 1, big, "הימור מינימלי"),
      limit: whole("labLimit", 1, big, "מגבלת שולחן"),
      ladder: state.ladder.slice(),
      afterWin: $("labAfterWin").value,
      atLimit: $("labAtLimit").value,
      short: $("labShort").value,
      freeze: state.freeze.map(function (e) { return e.slice(); }),
      freezeAfter: $("labFreezeAfter").value
    };
    if (policy.limit < policy.minBet) throw new Error("מגבלת השולחן קטנה מההימור המינימלי.");
    if (policy.start < policy.minBet) throw new Error("הכסף להתחלה לא מספיק להימור מינימלי.");
    if (!policy.ladder.length || policy.ladder.some(function (v) { return !(v >= 1); })) {
      throw new Error("בסולם ההימורים צריך שלב אחד לפחות, וכל שלב הוא מספר חיובי.");
    }
    if (policy.freeze.some(function (e) { return !(e[0] >= 1) || !(e[1] >= 1); })) {
      throw new Error("בכל שלב הקפאה צריכים להיות שני מספרים חיוביים: כמה רווח, וכמה להוציא הביתה. אפשר להסיר שלבים.");
    }
    var usable = policy.ladder.filter(function (v) { return v >= policy.minBet && v <= policy.limit; });
    if (!usable.length) throw new Error("אף שלב בסולם לא נמצא בין ההימור המינימלי למגבלת השולחן.");

    var out = {
      mode: mode(),
      chart: document.querySelector('input[name="chart"]:checked').value,
      rules: rulesFromForm(),
      policy: policy,
      overrides: Object.assign({}, state.overrides),
      handsPerDay: whole("labHands", 1, boot.limits.maxHands, "ידיים ביום"),
      seed: whole("labSeed", 0, 4294967295, "זרע")
    };
    if (out.mode === "days") {
      out.days = whole("labDays", 1, boot.limits.maxDays, "מספר ימים");
    } else {
      out.goal = $("labGoal").value;
      if (out.goal === "mix") {
        out.mix = {
          ahead: whole("labMixAhead", 0, 10, "משקל ימים ברווח"),
          avg: whole("labMixAvg", 0, 10, "משקל התוצאה הממוצעת"),
          survive: whole("labMixSurvive", 0, 10, "משקל משך הזמן")
        };
        if (!out.mix.ahead && !out.mix.avg && !out.mix.survive) throw new Error("לפחות משקל אחד צריך להיות גדול מאפס.");
      }
      out.days = whole("labSearchDays", 1, boot.limits.maxDays, "ימים לכל מדיניות");
      out.holdoutDays = whole("labHoldout", 1, boot.limits.maxDays, "ימים לבדיקה");
      out.budgetSeconds = whole("labBudget", 1, 300, "זמן חיפוש");
    }
    return out;
  }

  /* ---------- running ---------- */

  function fail(message) {
    var el = $("labError");
    el.textContent = message;
    el.hidden = !message;
  }

  function busy(on) {
    $("labRun").hidden = on;
    $("labStop").hidden = !on;
    $("labProgress").hidden = !on;
    if (!on) $("labProgress").value = 0;
  }

  function chartQuery(rules) {
    var q = new URLSearchParams();
    Object.keys(rules).forEach(function (k) {
      q.set(k, typeof rules[k] === "boolean" ? (rules[k] ? "1" : "0") : rules[k]);
    });
    return q.toString();
  }

  function run() {
    fail("");
    var form;
    try { form = readForm(); } catch (err) { fail(err.message); return; }
    $("labResults").hidden = true;
    state.result = null;
    busy(true);

    if (form.chart === "calculated") {
      // The browser works the chart out itself, in the worker, for any decks.
      var rules = Object.assign({}, boot.rules, form.rules, { double_any_two: true, surrender: "none", dealer_peeks: true });
      start(form, { rules: rules, cells: null }, true);
      return;
    }
    if ([4, 6, 8].indexOf(form.rules.decks) < 0) {
      busy(false);
      fail("לשולחן עם " + form.rules.decks + " חפיסות אין טבלה קלאסית. אפשר לבחור בטבלה מחושבת.");
      return;
    }
    $("labStatus").textContent = "מכינים את הטבלה...";

    fetch(root.dataset.chart + "?" + chartQuery(form.rules), { credentials: "same-origin" })
      .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.body.error || "אי אפשר להכין טבלה לכללים האלה.");
        start(form, res.body);
      })
      .catch(function (err) { busy(false); $("labStatus").textContent = ""; fail(err.message); });
  }

  function start(form, chart, calculate) {
    var cfg = {
      rules: chart.rules,
      policy: form.policy,
      overrides: form.overrides,
      handsPerDay: form.handsPerDay,
      days: form.days,
      seed: form.seed,
      chart: form.chart
    };
    if (form.mode === "search") {
      cfg.goal = form.goal;
      if (form.mix) cfg.mix = form.mix;
      cfg.holdoutDays = form.holdoutDays;
      cfg.maxTries = 5000;
      cfg.budgetMs = form.budgetSeconds * 1000;
    }
    state.cells = chart.cells;
    state.worker = new Worker(root.dataset.worker);
    state.worker.onmessage = function (event) { heard(event.data, form, cfg); };
    state.worker.onerror = function () { finish(); fail("הריצה נעצרה בגלל שגיאה בדפדפן."); };
    state.worker.postMessage({
      type: "start", core: new URL(root.dataset.core, location.href).href,
      best: new URL(root.dataset.best, location.href).href, calculate: !!calculate,
      mode: form.mode, cfg: cfg, cells: chart.cells
    });
    $("labStatus").textContent = "רצים...";
  }

  function finish() {
    if (state.worker) { state.worker.terminate(); state.worker = null; }
    busy(false);
  }

  function heard(msg, form, cfg) {
    if (msg.type === "progress") {
      if (msg.mode === "days") {
        $("labProgress").value = msg.played / msg.total;
        $("labStatus").textContent = "יום " + msg.played + " מתוך " + msg.total;
      } else {
        $("labProgress").value = Math.min(1, msg.ms / msg.budgetMs);
        $("labStatus").textContent = "ניסיונות: " + msg.tries + " · הטוב ביותר עד עכשיו: " +
          Math.round(msg.best.ahead * 100) + "% מהימים ברווח";
      }
    } else if (msg.type === "done") {
      finish();
      $("labStatus").textContent = "";
      state.result = { form: form, cfg: cfg, mode: msg.mode, result: msg.result };
      if (msg.mode === "days") showDays(state.result); else showSearch(state.result);
    } else if (msg.type === "stopped") {
      finish();
      $("labStatus").textContent = "נעצר.";
    } else if (msg.type === "error") {
      finish();
      $("labStatus").textContent = "";
      fail("משהו השתבש בריצה: " + msg.message);
    }
  }

  $("labRun").addEventListener("click", run);
  $("labStop").addEventListener("click", function () {
    if (state.worker) state.worker.postMessage({ type: "stop" });
  });

  /* ---------- showing a result ---------- */

  function saveBox() {
    return '<form class="bj-lab-save" id="labSaveForm" onsubmit="return false">' +
      '<label class="bj-field"><span>שם לריצה, אם רוצים</span><input id="labName" maxlength="80"></label>' +
      '<button type="button" id="labSave" class="bj-btn">שמירת התוצאה</button>' +
      '<p id="labSaved" class="bj-muted bj-small" aria-live="polite"></p></form>';
  }

  /* ---------- one day at a time, hand by hand (REQ-B.11.28) ----------

     Nothing about a single day was kept: the page plays the chosen day again
     from the run's seed, which gives the same cards, and draws it. Choosing
     another day, or closing the page, throws it away. */

  function dayPicker(days) {
    var html = '<section class="bj-day" id="daySection"><h2 class="bj-lab-h2">יום ביום</h2>' +
      '<p class="bj-muted bj-small">בחרו יום כדי לראות אותו יד אחרי יד: הכסף, ההימורים, והנקודות שבהן הוקפא כסף. אפשר לגרור, לצבוט ולהתקרב.</p>' +
      '<div class="bj-day-pick">' +
      '<button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayPrev">היום הקודם</button>' +
      '<label class="bj-sr" for="daySelect">איזה יום</label><select id="daySelect" class="bj-day-select">';
    days.forEach(function (d, i) {
      html += '<option value="' + i + '">יום ' + (i + 1) + " · " + fmt(d.total) + " · " + fmt(d.rounds) + " ידיים" +
        (d.frozen ? " · מוקפא " + fmt(d.frozen) : "") + "</option>";
    });
    html += '</select><button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayNext">היום הבא</button></div>' +
      '<div class="bj-day-quick">' +
      '<button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayBest">היום הכי טוב</button>' +
      '<button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayWorst">היום הכי גרוע</button>' +
      '<button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayLong">היום הכי ארוך</button></div>' +
      '<p class="bj-day-facts" id="dayFacts" aria-live="polite"></p><div id="dayView"></div></section>';
    return html;
  }

  var ENDED = { bust: "נגמר הכסף", limit: "הגיע למספר הידיים שנקבע", stopped: "המדיניות עצרה את המשחק" };

  function chartFor(res) {
    var cells = state.cells;
    if (!cells) cells = window.LabBest.calculate(res.cfg.rules).cells;
    return window.LabCore.makeChart(cells);
  }

  function showDay(res, index) {
    var chart = state.dayChart || (state.dayChart = chartFor(res));
    var one = window.LabCore.traceDay(res.cfg, chart, res.cfg.overrides, index);
    var twin = null;
    if (res.result.summary.changed) twin = window.LabCore.traceDay(res.cfg, chart, {}, index).trace;
    $("daySelect").value = String(index);
    $("dayFacts").textContent = "יום " + (index + 1) + ": " + fmt(one.result.rounds) + " ידיים. " + ENDED[one.result.ended] +
      ". השיא של הכסף למשחק " + fmt(one.result.peak) + ", השפל " + fmt(one.result.low) + ". הוקפאו " + fmt(one.result.frozen) +
      ", ובסך הכול נשארו " + fmt(one.result.total) + " (התחלתם עם " + fmt(res.cfg.policy.start) + ").";
    window.LabDay.mount($("dayView"), { trace: one.trace, result: one.result, classicTrace: twin });
    state.day = index;
  }

  function wireDays(res) {
    var days = res.result.temp.days;
    state.dayChart = null;
    $("daySelect").addEventListener("change", function () { showDay(res, parseInt($("daySelect").value, 10)); });
    $("dayPrev").addEventListener("click", function () { showDay(res, (state.day + days.length - 1) % days.length); });
    $("dayNext").addEventListener("click", function () { showDay(res, (state.day + 1) % days.length); });
    function pick(better) {
      var at = 0;
      days.forEach(function (d, i) { if (better(d, days[at])) at = i; });
      showDay(res, at);
    }
    $("dayBest").addEventListener("click", function () { pick(function (a, b) { return a.total > b.total; }); });
    $("dayWorst").addEventListener("click", function () { pick(function (a, b) { return a.total < b.total; }); });
    $("dayLong").addEventListener("click", function () { pick(function (a, b) { return a.rounds > b.rounds; }); });
    showDay(res, 0);
  }

  function showDays(res) {
    var s = res.result.summary, temp = res.result.temp;
    var html = Charts.daysTop(s) + Charts.trendFigure(s) + Charts.daysFigure(s, temp.curves) +
      Charts.histFigure(s) + dayPicker(temp.days) + saveBox();
    var box = $("labResults");
    box.innerHTML = html;
    box.hidden = false;
    $("labSave").addEventListener("click", function () { save(res); });
    wireDays(res);
    box.scrollIntoView({ block: "start" });
  }

  function showSearch(res) {
    var r = res.result;
    var html = Charts.searchBody(r);
    if (r.improved) html += '<button type="button" id="labUse" class="bj-btn bj-btn-small">להשתמש במדיניות הזו בטופס</button>';
    html += saveBox();
    var box = $("labResults");
    box.innerHTML = html;
    box.hidden = false;
    $("labSave").addEventListener("click", function () { save(res); });
    var use = $("labUse");
    if (use) use.addEventListener("click", function () {
      state.ladder = r.best.policy.ladder.slice();
      state.freeze = pairs(r.best.policy.freeze);
      renderLadder(); renderFreeze();
      document.querySelector('input[name="mode"][value="days"]').checked = true;
      showMode();
      window.scrollTo({ top: 0 });
    });
    box.scrollIntoView({ block: "start" });
  }

  /* ---------- saving: the conditions and the summary, and no more ---------- */

  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function save(res) {
    var form = res.form, cfg = res.cfg;
    var settings = {
      policy: form.policy, overrides: form.overrides,
      handsPerDay: form.handsPerDay, seed: form.seed, days: form.days, chart: form.chart
    };
    var summary;
    if (res.mode === "days") {
      summary = res.result.summary;
    } else {
      settings.goal = form.goal;
      if (form.mix) settings.mix = form.mix;
      settings.holdoutDays = form.holdoutDays;
      var r = res.result;
      summary = {
        tries: r.tries, ms: Math.round(r.ms), improved: r.improved,
        baseline: { train: r.baseline.train, holdout: r.baseline.holdout },
        best: { policy: r.best.policy, train: r.best.train, holdout: r.best.holdout }
      };
    }
    var body = {
      name: $("labName").value.trim(), mode: res.mode,
      rules_in: form.rules, settings: settings, summary: summary
    };
    $("labSave").disabled = true;
    fetch(root.dataset.api, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cookie("csrftoken") },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, data: data }; });
    }).then(function (out) {
      var note = $("labSaved");
      if (!out.ok) {
        $("labSave").disabled = false;
        var why = out.data;
        note.textContent = "לא נשמר: " + (Array.isArray(why) ? why[0] : (why.detail || JSON.stringify(why)));
        return;
      }
      note.textContent = "נשמר. ";
      var a = document.createElement("a");
      a.href = "/blackjack/lab/" + out.data.id + "/";
      a.textContent = "לפתיחת הריצה השמורה";
      note.appendChild(a);
    }).catch(function () {
      $("labSave").disabled = false;
      $("labSaved").textContent = "לא נשמר, אין חיבור.";
    });
  }

  fill();
})();
