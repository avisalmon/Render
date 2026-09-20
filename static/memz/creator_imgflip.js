/* Classic Imgflip templates in the solo creator (ACT-Z.5, spec §7.3). A
   second, self-contained panel next to the bank-image form: fetches the
   template list from memz's own API (a cached proxy of Imgflip's, no
   credentials needed to browse), lets a person pick one and type top/
   bottom text, and posts straight to /memz/api/imgflip/memes/ — Imgflip
   does the actual rendering, this file just wires the picker. */
(function () {
  "use strict";

  var toggle = document.querySelector("[data-creator-source-toggle]");
  if (!toggle) return;

  var panels = {
    bank: document.querySelector('[data-creator-source-panel="bank"]'),
    imgflip: document.querySelector('[data-creator-source-panel="imgflip"]'),
  };
  var buttons = toggle.querySelectorAll("[data-creator-source-btn]");

  function showSource(name) {
    Object.keys(panels).forEach(function (key) {
      if (panels[key]) panels[key].hidden = key !== name;
    });
    buttons.forEach(function (btn) {
      var active = btn.dataset.creatorSourceBtn === name;
      btn.classList.toggle("memz-btn--primary", active);
      btn.classList.toggle("memz-btn--secondary", !active);
    });
  }

  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () { showSource(btn.dataset.creatorSourceBtn); });
  });

  var grid = document.querySelector("[data-imgflip-thumb-grid]");
  var loadingMsg = document.querySelector("[data-imgflip-loading]");
  var topInput = document.querySelector("[data-imgflip-top]");
  var bottomInput = document.querySelector("[data-imgflip-bottom]");
  var errorEl = document.querySelector("[data-imgflip-error]");
  var submitBtn = document.querySelector("[data-imgflip-submit]");
  if (!grid || !submitBtn) return;

  var selectedId = null;

  // ACT-Z.20: templates sit below the caption fields and the button now,
  // so picking one shows it at the top and scrolls you back to it —
  // this panel has no live preview canvas, so without the chosen image
  // there would be nothing up there to have gone back for.
  var chosenWrap = document.querySelector("[data-imgflip-chosen]");
  var chosenImage = document.querySelector("[data-imgflip-chosen-image]");

  function selectTemplate(li, id, url) {
    grid.querySelectorAll(".memz-thumb--selected").forEach(function (el) {
      el.classList.remove("memz-thumb--selected");
    });
    li.classList.add("memz-thumb--selected");
    selectedId = id;
    submitBtn.disabled = false;

    if (chosenWrap && chosenImage && url) {
      chosenImage.src = url;
      chosenWrap.hidden = false;
    }
    var top = document.querySelector("[data-creator-top]");
    if (top && top.scrollIntoView) {
      var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      top.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }
  }

  window.memz.api("GET", "/memz/api/imgflip/templates/").then(function (data) {
    if (loadingMsg) loadingMsg.hidden = true;
    (data.templates || []).forEach(function (t) {
      var li = document.createElement("li");
      li.className = "memz-thumb";
      var img = document.createElement("img");
      img.src = t.url;
      img.alt = t.name || "";
      img.loading = "lazy";
      li.appendChild(img);
      li.addEventListener("click", function () { selectTemplate(li, t.id, t.url); });
      grid.appendChild(li);
    });
    if (!data.templates || !data.templates.length) {
      if (loadingMsg) {
        loadingMsg.hidden = false;
        loadingMsg.textContent = "אין כרגע תבניות זמינות.";
      }
    }
  }).catch(function () {
    if (loadingMsg) {
      loadingMsg.hidden = false;
      loadingMsg.textContent = "לא הצלחנו לטעון תבניות כרגע.";
    }
  });

  submitBtn.addEventListener("click", function () {
    if (!selectedId || submitBtn.disabled) return;
    errorEl.hidden = true;
    submitBtn.disabled = true; // Rule 11.1: never a second submit in flight
    window.memz.api("POST", "/memz/api/imgflip/memes/", {
      template_id: selectedId,
      top_text: topInput ? topInput.value : "",
      bottom_text: bottomInput ? bottomInput.value : "",
    }).then(function (meme) {
      window.location.href = "/memz/create/" + meme.share_slug + "/";
    }).catch(function (err) {
      submitBtn.disabled = false;
      var msg = (err.data && err.data.detail) || (err.data && err.data.template_id) || "משהו השתבש, נסו שוב.";
      errorEl.textContent = msg;
      errorEl.hidden = false;
    });
  });

  showSource("bank");
})();
