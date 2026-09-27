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
  const map = {
    limit: document.documentElement.lang === "he"
      ? "הגעת למגבלה להיום. נסה שוב מחר."
      : "You've hit today's limit. Try again tomorrow.",
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

/* ---- stage 1: the interview --------------------------------------- */

function exoInterview() {
  const chat = document.getElementById("chat");
  const box = document.getElementById("say");
  const send = document.getElementById("send");
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

  const regen = document.getElementById("regen");
  if (regen) {
    regen.addEventListener("click", async () => {
      try {
        await exo.api(root.dataset.generate, { method: "POST", json: {} });
        window.location.reload();
      } catch (err) {
        if (err.status === 409) {
          // Edited by hand: ask before overwriting, never silently.
          if (window.confirm(regen.dataset.warn || "Overwrite your edits?")) {
            try {
              await exo.api(root.dataset.generate, {
                method: "POST",
                json: { confirm: true },
              });
              window.location.reload();
            } catch (e2) {
              exoToastError(e2);
            }
          }
          return;
        }
        exoToastError(err);
      }
    });
  }

  const edit = document.getElementById("edit");
  if (edit) {
    edit.addEventListener("click", async () => {
      const paper = document.querySelector(".exo-paper-body");
      const head = document.querySelector(".exo-paper-headline");
      const editing = edit.dataset.editing === "1";
      if (!editing) {
        paper.contentEditable = "true";
        head.contentEditable = "true";
        paper.focus();
        edit.dataset.editing = "1";
        edit.classList.add("is-on");
        return;
      }
      paper.contentEditable = "false";
      head.contentEditable = "false";
      edit.dataset.editing = "0";
      edit.classList.remove("is-on");
      try {
        await exo.api(root.dataset.edit, {
          method: "POST",
          json: { headline: head.innerText, body: paper.innerText },
        });
        exo.toast(document.documentElement.lang === "he" ? "נשמר" : "Saved", "ok");
      } catch (err) {
        exoToastError(err);
      }
    });
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
