/* exo — the journey's behaviour.
 *
 * One file, no framework, no build step. Every function here is called
 * explicitly by the page that needs it, so a screen only runs its own code
 * and a bug in one stage cannot break another.
 *
 * The rule throughout: the server owns the truth. Nothing here holds journey
 * state — every action posts and then reflects what came back. A refresh is
 * always safe.
 */

/* global exo */

function exoToastError(err) {
  const he = document.documentElement.lang === "he";

  /* A stage limit names the stage and the number, because "you hit a limit"
     tells a person nothing they can act on. */
  if (err && err.detail === "limit_stage") {
    const stage = {
      options: he ? "יצירת אפשרויות למאפיין הזה" : "generating options for this attribute",
      output: he ? "הפקת ההודעה לעיתונות לרעיון הזה" : "generating the press release for this idea",
      stress_test: he ? "מבחן הלקוח לרעיון הזה" : "the stress test for this idea",
    }[err.task] || (he ? "השלב הזה" : "this stage");
    exo.toast(
      he
        ? `${stage} הגיעה למכסה היומית (${err.ceiling}). נסה שוב מחר, או פתח רעיון חדש.`
        : `${stage} has reached its daily ceiling (${err.ceiling}). Try tomorrow, or start a new idea.`,
      "error"
    );
    return;
  }

  const map = {
    limit: document.documentElement.lang === "he"
      ? "הגעת למגבלה להיום. נסה שוב מחר."
      : "You've hit today's limit. Try again tomorrow.",
    limit_member: document.documentElement.lang === "he"
      ? "הגעת למכסת הבקשות היומית שלך. היא מתאפסת בעוד 24 שעות."
      : "You have used your daily requests. They reset within 24 hours.",
    limit_site: document.documentElement.lang === "he"
      ? "האתר כולו הגיע למכסה היומית. שאר האפליקציה עובדת כרגיל."
      : "The whole site has reached its daily ceiling. Everything else still works.",
    ai: document.documentElement.lang === "he"
      ? "ה-AI עמוס כרגע. נסה שוב בעוד רגע."
      : "The AI is busy right now. Try again in a moment.",
    mtp_too_long: document.documentElement.lang === "he"
      ? "המטרה ארוכה מדי. סלוגן של עד שבע מילים."
      : "The purpose is too long. A slogan of seven words at most.",
    note_too_long: document.documentElement.lang === "he"
      ? "משפט ההרחבה ארוך מדי. עד חמש־עשרה מילים."
      : "The expansion is too long. Fifteen words at most.",
  };
  exo.toast(map[err && err.message] || (err && err.message) || "Error", "error");
}

/* ---- drafts: what you typed but never sent -------------------------- *
 *
 * Everything in this journey is stored server-side the moment it is sent, so
 * nothing committed is ever lost. What used to be lost is the sentence still
 * sitting in the box when a tab closes, and that is the one that stings:
 * it is the thought you were in the middle of.
 *
 * Kept in this browser only, per concept. It is a convenience, not state the
 * app depends on, so every access is wrapped: a private window, cleared site
 * data or a blocked store must not break the page, only forget a draft.
 */
const exoDraft = {
  key(scope, id) { return "exo.draft." + scope + "." + id; },
  read(scope, id) {
    try { return window.localStorage.getItem(this.key(scope, id)) || ""; }
    catch (e) { return ""; }
  },
  write(scope, id, value) {
    try {
      if (value && value.trim()) {
        window.localStorage.setItem(this.key(scope, id), value);
      } else {
        window.localStorage.removeItem(this.key(scope, id));
      }
    } catch (e) { /* no store: the draft is simply not kept */ }
  },
  clear(scope, id) { this.write(scope, id, ""); },
};

/* ---- stage 1: the interview --------------------------------------- */

function exoInterview() {
  const chat = document.getElementById("chat");
  const box = document.getElementById("say");
  const send = document.getElementById("send");
  const conceptId = chat.dataset.concept || "0";

  // An answer half-typed when the tab closed is waiting where it was left.
  box.value = exoDraft.read("say", conceptId);
  box.addEventListener("input", () => exoDraft.write("say", conceptId, box.value));
  const sheet = document.getElementById("settle");
  const open = document.getElementById("settle-open");

  function bubble(role, text) {
    const el = document.createElement("div");
    el.className = "exo-msg exo-msg-" + role;
    el.textContent = text;
    chat.appendChild(el);
    el.scrollIntoView({ block: "end", behavior: "smooth" });
    return el;
  }

  async function say() {
    const text = (box.value || "").trim();
    if (!text) return;
    box.value = "";
    exoDraft.clear("say", conceptId);
    bubble("user", text);
    const thinking = bubble("assistant", "…");
    thinking.classList.add("is-thinking");
    send.disabled = true;
    try {
      const data = await exo.api(chat.dataset.send, { method: "POST", json: { text } });
      thinking.classList.remove("is-thinking");
      thinking.textContent = data.reply;
    } catch (err) {
      // The user's turn is already saved server-side; only the reply failed.
      thinking.remove();
      exoToastError(err);
    } finally {
      send.disabled = false;
      box.focus();
    }
  }

  send.addEventListener("click", say);
  box.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      say();
    }
  });

  const accept = document.getElementById("settle-accept");

  /* The MTP is a slogan and the note is one line. Counting words as they are
     typed, and refusing to submit while either is over, means the rule is
     visible before it is enforced. Discovering a limit by being rejected
     after writing is the worst way to learn one. */
  function countWords(value) {
    return (value || "").trim().split(/\s+/).filter(Boolean).length;
  }

  function watchLength(fieldId, counterId) {
    const field = document.getElementById(fieldId);
    const counter = document.getElementById(counterId);
    if (!field || !counter) return () => true;
    const max = Number(counter.dataset.max || 0);

    function update() {
      const n = countWords(field.value);
      counter.textContent = n + " / " + max;
      const over = n > max;
      counter.classList.toggle("is-over", over);
      return !over;
    }
    field.addEventListener("input", () => { update(); refresh(); });
    update();
    return update;
  }

  /* The settle sheet is where a person writes their purpose in their own
     words. Losing that to a closed tab is losing the most considered
     sentence in the whole journey. */
  const SETTLE_FIELDS = ["f-mtp", "f-mtp-note", "f-special", "f-unique"];
  SETTLE_FIELDS.forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;
    const saved = exoDraft.read(id, conceptId);
    if (saved && !field.value.trim()) field.value = saved;
    field.addEventListener("input", () => exoDraft.write(id, conceptId, field.value));
  });
  function clearSettleDrafts() {
    SETTLE_FIELDS.forEach((id) => exoDraft.clear(id, conceptId));
  }

  let checks = [];
  function refresh() {
    const ok = checks.every((check) => check());
    accept.disabled = !ok;
  }
  checks = [
    watchLength("f-mtp", "c-mtp"),
    watchLength("f-mtp-note", "c-mtp-note"),
  ];
  refresh();

  open.addEventListener("click", async () => {
    sheet.hidden = false;
    // Only ask the model if the person has not already settled it once.
    if (!document.getElementById("f-mtp").value.trim()) {
      try {
        const data = await exo.api(open.dataset.summary, { method: "POST" });
        document.getElementById("f-mtp").value = data.mtp || "";
        document.getElementById("f-mtp-note").value = data.mtp_note || "";
        document.getElementById("f-special").value = data.special || "";
        document.getElementById("f-unique").value = data.unique || "";
        refresh();
      } catch (err) {
        exoToastError(err);
      }
    }
  });

  document.getElementById("settle-close").addEventListener("click", () => {
    sheet.hidden = true;
  });

  accept.addEventListener("click", async (e) => {
    e.target.disabled = true;
    try {
      const data = await exo.api(sheet.dataset.accept, {
        method: "POST",
        json: {
          mtp: document.getElementById("f-mtp").value,
          mtp_note: document.getElementById("f-mtp-note").value,
          special: document.getElementById("f-special").value,
          unique: document.getElementById("f-unique").value,
        },
      });
      clearSettleDrafts();
      window.location = data.next;
    } catch (err) {
      e.target.disabled = false;
      exoToastError(err);
    }
  });

  chat.scrollTop = chat.scrollHeight;
}

/* ---- stage 2: the brainstorm --------------------------------------- */

function exoBrainstorm() {
  const root = document.getElementById("slots");
  const slots = Array.from(root.querySelectorAll(".exo-slot"));
  const addUrl = root.dataset.add;
  const conceptId = root.dataset.concept;
  let index = 0;

  // One slot at a time only where the screen is narrow; CSS decides, and this
  // just keeps the pointer in step with it.
  const narrow = () => window.matchMedia("(max-width: 899px)").matches;

  function show() {
    if (!narrow()) {
      slots.forEach((s) => s.removeAttribute("data-hidden-mobile"));
      document.getElementById("slotnav").hidden = true;
      return;
    }
    document.getElementById("slotnav").hidden = false;
    slots.forEach((s, i) => {
      if (i === index) s.removeAttribute("data-hidden-mobile");
      else s.setAttribute("data-hidden-mobile", "1");
    });
    document.getElementById("slotpos").textContent = index + 1 + " / " + slots.length;
  }

  document.getElementById("prev").addEventListener("click", () => {
    index = Math.max(0, index - 1);
    show();
  });
  document.getElementById("next").addEventListener("click", () => {
    index = Math.min(slots.length - 1, index + 1);
    show();
  });
  window.addEventListener("resize", show);
  show();

  function countFilled() {
    const n = slots.filter((s) => s.querySelectorAll(".exo-entries li").length).length;
    document.getElementById("filled").textContent = n;
  }

  slots.forEach((slot) => {
    const key = slot.dataset.key;
    const input = slot.querySelector(".exo-entry-add input");
    const button = slot.querySelector("[data-add-btn]");
    const list = slot.querySelector(".exo-entries");

    async function add() {
      const text = (input.value || "").trim();
      if (!text) return;
      input.value = "";
      try {
        const data = await exo.api(addUrl, {
          method: "POST",
          json: { attribute: key, text },
        });
        const li = document.createElement("li");
        li.dataset.id = data.id;
        li.innerHTML =
          '<span class="exo-entry-text"></span>' +
          '<button class="exo-icon-btn exo-icon-danger" data-delete="' +
          data.id + '" aria-label="✕">✕</button>';
        li.querySelector(".exo-entry-text").textContent = data.text;
        list.appendChild(li);
        countFilled();
      } catch (err) {
        exoToastError(err);
      }
    }

    button.addEventListener("click", add);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        add();
      }
    });

    list.addEventListener("click", async (e) => {
      const del = e.target.closest("[data-delete]");
      if (!del) return;
      const id = del.dataset.delete;
      try {
        await exo.api(
          "/exo/concepts/" + conceptId + "/entries/" + id + "/delete/",
          { method: "POST" }
        );
        del.closest("li").remove();
        countFilled();
      } catch (err) {
        exoToastError(err);
      }
    });
  });
}

/* ---- stage 3: options and selection -------------------------------- */

function exoOptions() {
  const root = document.getElementById("slots");
  const genUrl = root.dataset.generate;
  const ownUrl = root.dataset.own;
  const selectTemplate = root.dataset.select;
  const dropTemplate = root.dataset.dropUrl;

  /* Must stay the same shape as the server-rendered row in options.html.
     Two renderers for one component is a standing hazard in this file; the
     day that matters, both have to produce a row that the click handlers
     below can read. */
  function optionEl(o) {
    const row = document.createElement("div");
    row.className = "exo-option-row";

    const b = document.createElement("button");
    b.type = "button";
    b.className = "exo-option" + (o.is_selected ? " is-selected" : "");
    b.dataset.option = o.id;
    b.setAttribute("role", "checkbox");
    b.setAttribute("aria-checked", o.is_selected ? "true" : "false");
    const why = o.research_note
      ? '<span class="exo-option-why"></span>'
      : "";
    b.innerHTML =
      '<span class="exo-option-check" aria-hidden="true"></span>' +
      '<span class="exo-option-body"><span class="exo-option-text"></span>' + why +
      (o.is_user_authored ? '<span class="exo-option-mine">✎</span>' : "") +
      "</span>";
    b.querySelector(".exo-option-text").textContent = o.content;
    if (o.research_note) b.querySelector(".exo-option-why").textContent = o.research_note;

    const drop = document.createElement("button");
    drop.type = "button";
    drop.className = "exo-option-drop";
    drop.dataset.drop = o.id;
    drop.textContent = "✕";
    drop.setAttribute("aria-label", root.dataset.dropLabel || "Remove");
    drop.title = drop.getAttribute("aria-label");

    row.appendChild(b);
    row.appendChild(drop);
    return row;
  }

  function recount() {
    const n = Array.from(root.querySelectorAll(".exo-slot")).filter((s) =>
      s.querySelector(".exo-option.is-selected")
    ).length;
    document.getElementById("withsel").textContent = n;
  }

  root.querySelectorAll(".exo-slot").forEach((slot) => {
    const key = slot.dataset.key;
    const list = slot.querySelector("[data-list]");
    const gen = slot.querySelector("[data-gen]");
    const own = slot.querySelector("[data-own-btn]");
    const leftLabel = slot.querySelector("[data-left-label]");

    function setLeft(n) {
      if (n === undefined || n === null) return;
      gen.dataset.left = n;
      gen.disabled = n <= 0;
      if (leftLabel) {
        leftLabel.textContent = n > 0
          ? n + "/" + (root.dataset.perSlot || n)
          : (root.dataset.noMore || "");
      }
    }

    gen.addEventListener("click", async () => {
      const label = gen.textContent;
      gen.disabled = true;
      gen.textContent = "…";
      try {
        // Per slot on purpose: each arrives on its own, and one slot failing
        // is one slot's problem (spec §5.3, D3.4).
        const data = await exo.api(genUrl, {
          method: "POST",
          json: { attribute: key },
        });
        // Appended, never assigned over: the list on screen keeps everything
        // it already has, so a new batch cannot disturb a tick.
        (data.added || []).forEach((o) => list.appendChild(optionEl(o)));
        setLeft(data.left);
        recount();
      } catch (err) {
        exoToastError(err);
      } finally {
        gen.disabled = false;
        gen.textContent = label;
      }
    });

    own.addEventListener("click", async () => {
      const text = window.prompt(own.textContent);
      if (!text || !text.trim()) return;
      try {
        const o = await exo.api(ownUrl, {
          method: "POST",
          json: { attribute: key, text: text.trim() },
        });
        list.appendChild(optionEl(o));
        recount();
      } catch (err) {
        exoToastError(err);
      }
    });

    list.addEventListener("click", async (e) => {
      const drop = e.target.closest(".exo-option-drop");
      if (drop) {
        const row = drop.closest(".exo-option-row");
        try {
          await exo.api(dropTemplate.replace("OPTION", drop.dataset.drop),
                        { method: "POST" });
          row.remove();
          recount();
        } catch (err) {
          exoToastError(err);
        }
        return;
      }

      const el = e.target.closest(".exo-option");
      if (!el) return;
      try {
        const data = await exo.api(
          selectTemplate.replace("OPTION", el.dataset.option),
          { method: "POST" }
        );
        el.classList.toggle("is-selected", data.is_selected);
        el.setAttribute("aria-checked", data.is_selected ? "true" : "false");
        recount();
      } catch (err) {
        exoToastError(err);
      }
    });
  });
}

/* ---- stage 4: the output ------------------------------------------- */

function exoOutput() {
  const root = document.getElementById("outputroot");
  const generate = document.getElementById("generate");

  if (generate) {
    generate.addEventListener("click", async () => {
      generate.disabled = true;
      const state = document.getElementById("genstate");
      state.textContent = generate.dataset.working || "…";
      try {
        await exo.api(root.dataset.generate, { method: "POST", json: {} });
        window.location.reload();
      } catch (err) {
        generate.disabled = false;
        state.textContent = "";
        exoToastError(err);
      }
    });
    return;
  }

  const style = document.getElementById("style");
  if (style) {
    style.addEventListener("change", async () => {
      try {
        const data = await exo.api(root.dataset.style, {
          method: "POST",
          json: { style: style.value },
        });
        const paper = document.querySelector(".exo-paper");
        // Swap only the style class — the content is untouched, which is the
        // whole promise of switching papers.
        paper.className = "exo-paper " + data.css_class;
      } catch (err) {
        exoToastError(err);
      }
    });
  }

  const stress = document.getElementById("stress");
  if (stress) {
    stress.addEventListener("click", async () => {
      stress.disabled = true;
      try {
        const data = await exo.api(root.dataset.stress, { method: "POST" });
        const host = document.getElementById("stresspoints");
        const ul = document.createElement("ul");
        ul.className = "exo-points";
        data.points.forEach((p) => {
          const li = document.createElement("li");
          li.textContent = p;
          ul.appendChild(li);
        });
        host.innerHTML = "";
        host.appendChild(ul);
      } catch (err) {
        exoToastError(err);
      } finally {
        stress.disabled = false;
      }
    });
  }

  /* "Write a new feature", in both places it appears: above the article and
     below it. One behaviour, bound to every copy, because two buttons that
     drift apart is how one of them quietly stops working.

     It always asks first. Replacing a piece somebody has read, shown to
     someone, or is about to publish is not something to do on a single click,
     and a second, stronger question is asked if they edited it by hand. */
  const regens = Array.from(document.querySelectorAll("[data-regen]"));
  const states = Array.from(document.querySelectorAll("[data-genstate]"));

  function working(on, label) {
    regens.forEach((b) => { b.disabled = on; });
    states.forEach((s) => { s.textContent = on ? label : ""; });
  }

  async function writeNew(button) {
    if (!window.confirm(button.dataset.confirm)) return;
    working(true, button.dataset.working || "…");
    try {
      await exo.api(root.dataset.generate, { method: "POST", json: {} });
      window.location.reload();
    } catch (err) {
      if (err.status === 409) {
        // Edited by hand: ask the stronger question, never overwrite silently.
        working(false);
        if (!window.confirm(button.dataset.warn)) return;
        working(true, button.dataset.working || "…");
        try {
          await exo.api(root.dataset.generate, {
            method: "POST",
            json: { confirm: true },
          });
          window.location.reload();
          return;
        } catch (e2) {
          working(false);
          exoToastError(e2);
          return;
        }
      }
      working(false);
      exoToastError(err);
    }
  }

  regens.forEach((b) => b.addEventListener("click", () => writeNew(b)));

  /* ---- editing the article ------------------------------------------
     Editing used to be `contentEditable` switched on over the printed piece:
     one button that meant both "start" and "save", no cancel, and nothing to
     get back to if you changed your mind halfway.

     This edits the article as what it actually is: a headline and a list of
     paragraphs. That is the unit it is stored in, blank-line separated, and
     the unit the page, the PDF and the Word file all read, so reordering and
     deleting need no new format and cannot make the three disagree. */
  const editor = document.getElementById("editor");
  const edit = document.getElementById("edit");

  if (editor && edit) {
    const paras = document.getElementById("ed-paragraphs");
    const headlineBox = document.getElementById("ed-headline");
    const counter = document.getElementById("ed-count");
    const paperEl = document.getElementById("paper");
    const releaseId = editor.dataset.release;
    const label = (key, fallback) =>
      document.documentElement.lang === "he" ? key : fallback;

    let opened = "";   // what the article looked like when editing began

    function autosize(box) {
      box.style.height = "auto";
      box.style.height = box.scrollHeight + "px";
    }

    function autosizeAll() {
      rows().forEach(autosize);
    }

    /* Measured twice on purpose. The first pass runs with whatever font is
       available at that instant, and this page loads a serif from the network;
       when it arrives every line gets taller and each box is left clipped
       showing two rows of a five-row paragraph. `document.fonts.ready`
       settles after the real face is in, so the second pass measures the text
       people will actually see. Resizing changes the wrap, so that re-measures
       too. */
    function autosizeWhenSettled() {
      autosizeAll();
      if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(autosizeAll);
      }
      window.requestAnimationFrame(autosizeAll);
    }

    window.addEventListener("resize", () => {
      if (!editor.hidden) autosizeAll();
    });

    function countWords() {
      const text = [headlineBox.value]
        .concat(rows().map((b) => b.value))
        .join(" ");
      const n = text.trim().split(/\s+/).filter(Boolean).length;
      counter.textContent = n + " " + (editor.dataset.wordLabel || "");
    }

    function rows() {
      return Array.from(paras.querySelectorAll("textarea"));
    }

    function snapshot() {
      return JSON.stringify({
        headline: headlineBox.value,
        body: rows().map((b) => b.value.trim()).filter(Boolean).join("\n\n"),
      });
    }

    function addRow(text, before) {
      const row = document.createElement("div");
      row.className = "exo-para";

      const box = document.createElement("textarea");
      box.rows = 2;
      box.value = text || "";
      box.addEventListener("input", () => {
        autosize(box);
        countWords();
        saveDraft();
      });

      const tools = document.createElement("div");
      tools.className = "exo-para-tools";
      [
        ["up", "↑", editor.dataset.labelUp],
        ["down", "↓", editor.dataset.labelDown],
        ["del", "✕", editor.dataset.labelDel],
      ].forEach(([action, glyph, title]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "exo-icon-btn";
        button.textContent = glyph;
        button.title = title || action;
        button.setAttribute("aria-label", title || action);
        button.addEventListener("click", () => {
          if (action === "up" && row.previousElementSibling) {
            paras.insertBefore(row, row.previousElementSibling);
          } else if (action === "down" && row.nextElementSibling) {
            paras.insertBefore(row.nextElementSibling, row);
          } else if (action === "del") {
            row.remove();
            if (!rows().length) addRow("");
          }
          countWords();
          saveDraft();
          box.focus();
        });
        tools.appendChild(button);
      });

      row.appendChild(box);
      row.appendChild(tools);
      paras.insertBefore(row, before || null);
      autosize(box);
      return box;
    }

    function load(headline, body) {
      headlineBox.value = headline;
      paras.innerHTML = "";
      const blocks = (body || "").split(/\n\s*\n/).map((b) => b.trim())
        .filter(Boolean);
      (blocks.length ? blocks : [""]).forEach((b) => addRow(b));
      autosizeWhenSettled();
      countWords();
    }

    /* The draft survives a closed tab, like the interview box does. It is a
       convenience and never state the app depends on, so every access is
       wrapped. */
    const draftKey = "article." + releaseId;
    function saveDraft() { exoDraft.write(draftKey, "v1", snapshot()); }

    function open() {
      const current = {
        headline: document.querySelector(".exo-paper-headline").innerText.trim(),
        body: Array.from(document.querySelectorAll(".exo-paper-body p"))
          .map((p) => p.innerText.trim()).filter(Boolean).join("\n\n"),
      };
      const saved = exoDraft.read(draftKey, "v1");
      let start = current;
      if (saved) {
        try { start = JSON.parse(saved); } catch (e) { start = current; }
      }
      // Shown *before* filling: a textarea inside a hidden element reports a
      // scrollHeight of zero, so auto-sizing it there measures nothing and
      // every paragraph opens clipped to two rows.
      editor.hidden = false;
      paperEl.hidden = true;
      load(start.headline, start.body);
      opened = JSON.stringify(current);
      edit.classList.add("is-on");
      headlineBox.focus();
    }

    function close() {
      editor.hidden = true;
      paperEl.hidden = false;
      edit.classList.remove("is-on");
    }

    edit.addEventListener("click", () => (editor.hidden ? open() : close()));

    document.getElementById("ed-add").addEventListener("click", () => {
      addRow("").focus();
      saveDraft();
    });

    document.getElementById("ed-cancel").addEventListener("click", () => {
      if (snapshot() !== opened && !window.confirm(editor.dataset.confirmCancel)) {
        return;
      }
      exoDraft.clear(draftKey, "v1");
      close();
    });

    document.getElementById("ed-save").addEventListener("click", async (e) => {
      const payload = JSON.parse(snapshot());
      if (!payload.body.trim()) {
        exo.toast(editor.dataset.emptyWarning, "error");
        return;
      }
      e.target.disabled = true;
      try {
        await exo.api(root.dataset.edit, { method: "POST", json: payload });
        exoDraft.clear(draftKey, "v1");
        window.location.reload();
      } catch (err) {
        e.target.disabled = false;
        exoToastError(err);
      }
    });

    // Escape closes, asking first if anything changed.
    editor.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") document.getElementById("ed-cancel").click();
    });

    headlineBox.addEventListener("input", () => { countWords(); saveDraft(); });
  }

  const radios = document.querySelectorAll('input[name="visibility"]');
  const timed = document.getElementById("timedrow");
  const specific = document.getElementById("specificrow");
  radios.forEach((r) =>
    r.addEventListener("change", () => {
      timed.hidden = r.value !== "timed";
      specific.hidden = r.value !== "specific";
    })
  );

  const save = document.getElementById("savevis");
  if (save) {
    save.addEventListener("click", async () => {
      const chosen = document.querySelector('input[name="visibility"]:checked');
      if (!chosen) return;
      const payload = { visibility: chosen.value };
      if (chosen.value === "timed") {
        payload.hours = parseInt(document.getElementById("hours").value, 10);
      }
      if (chosen.value === "specific") {
        payload.emails = (document.getElementById("emails").value || "")
          .split(/[,\s]+/)
          .filter(Boolean);
      }
      try {
        await exo.api(root.dataset.visibility, { method: "POST", json: payload });
        exo.toast(document.documentElement.lang === "he" ? "נשמר" : "Saved", "ok");
        window.location.reload();
      } catch (err) {
        exoToastError(err);
      }
    });
  }
}

/* ---- the museum item ----------------------------------------------- */

function exoMuseumItem() {
  const root = document.getElementById("itemactions");
  const like = document.getElementById("like");

  like.addEventListener("click", async () => {
    if (like.dataset.anon === "1") {
      // A gentle nudge on tap, never a standing banner (spec §7.3, F3.1).
      exo.toast(root.dataset.signin);
      return;
    }
    try {
      const data = await exo.api(root.dataset.like, { method: "POST" });
      like.classList.toggle("is-on", data.liked);
      document.getElementById("likecount").textContent = data.likes;
    } catch (err) {
      exoToastError(err);
    }
  });

  document.getElementById("share").addEventListener("click", async () => {
    const url = window.location.href;
    const title = document.title;
    if (navigator.share) {
      try {
        await navigator.share({ title, url });
        return;
      } catch (e) {
        /* the person cancelled the sheet; fall through to copying */
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      exo.toast(document.documentElement.lang === "he" ? "הקישור הועתק" : "Link copied", "ok");
    } catch (e) {
      window.prompt("", url);
    }
  });
}
