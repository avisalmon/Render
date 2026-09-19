/* The profile page's actions: everything here calls the REST API and
   patches the DOM itself — no location.reload() after an action (spec
   Rule 11.1: a tap never costs you your place). */
(function () {
  "use strict";

  function bumpCount(selector, delta) {
    var el = document.querySelector(selector);
    if (!el) return;
    var m = el.textContent.match(/\((\d+)\/(\d+|∞)\)/);
    if (!m) return;
    el.textContent = el.textContent.replace(m[0], "(" + (parseInt(m[1], 10) + delta) + "/" + m[2] + ")");
  }

  // ---------------------------------------------------------------- unsave
  document.querySelectorAll("[data-unsave]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      btn.disabled = true;
      try {
        await window.memz.api("DELETE", "/memz/api/saved/" + btn.dataset.unsave + "/");
        var row = document.querySelector('[data-saved-row="' + btn.dataset.unsave + '"]');
        if (row) row.remove();
      } catch (e) {
        btn.disabled = false;
      }
    });
  });

  // (Uploading and deleting images left this page in ACT-Z.18: the
  // library has its own screen now, /memz/images/, driven by library.js.
  // This page shows a handful of thumbnails and links to it.)

  // ------------------------------------------------------------ delete pack
  document.querySelectorAll("[data-delete-pack]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      btn.disabled = true;
      try {
        await window.memz.api("DELETE", "/memz/api/packs/" + btn.dataset.deletePack + "/");
        btn.closest("li").remove();
        bumpCount("[data-pack-count]", -1);
      } catch (e) {
        btn.disabled = false;
      }
    });
  });

  // ------------------------------------------------------------ create pack
  var packForm = document.querySelector("[data-pack-form]");
  if (packForm) {
    packForm.querySelector("[data-pack-submit]").addEventListener("click", async function () {
      var input = packForm.querySelector("[data-pack-name]");
      var name = input.value.trim();
      if (!name) return;
      try {
        var pack = await window.memz.api("POST", "/memz/api/packs/", { name: name });
        var list = document.querySelector("#my-bank .memz-player-list");
        if (!list) {
          list = document.createElement("ul");
          list.className = "memz-player-list";
          packForm.insertAdjacentElement("afterend", list);
        }
        var li = document.createElement("li");
        li.className = "memz-player-row";
        li.innerHTML = '<span></span><button type="button" class="memz-btn memz-btn--ghost memz-btn--small" data-delete-pack="' + pack.id + '">מחיקה</button>';
        li.querySelector("span").textContent = pack.name + " (0)";
        list.appendChild(li);
        bumpCount("[data-pack-count]", 1);
        li.querySelector("[data-delete-pack]").addEventListener("click", async function () {
          await window.memz.api("DELETE", "/memz/api/packs/" + pack.id + "/");
          li.remove();
          bumpCount("[data-pack-count]", -1);
        });
        input.value = "";
      } catch (e) {
        // the cap or a validation error; the field itself shows nothing fancier for now
      }
    });
  }

})();
