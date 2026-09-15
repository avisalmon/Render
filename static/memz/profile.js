/* The profile page's actions: everything here calls the REST API and
   patches the DOM itself — no location.reload() after an action (spec
   Rule 11.1: a tap never costs you your place). */
(function () {
  "use strict";

  var STATUS_LABEL = { approved: "אושרה", rejected: "נדחתה", pending: "בבדיקה" };

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

  // ------------------------------------------------------------- delete img
  document.querySelectorAll("[data-delete-image]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      btn.disabled = true;
      try {
        await window.memz.api("DELETE", "/memz/api/images/" + btn.dataset.deleteImage + "/");
        var row = document.querySelector('[data-bank-row="' + btn.dataset.deleteImage + '"]');
        if (row) row.remove();
        bumpCount("[data-bank-count]", -1);
      } catch (e) {
        btn.disabled = false;
      }
    });
  });

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

  // ----------------------------------------------------------------- upload
  var uploadForm = document.querySelector("[data-upload-form]");
  if (uploadForm) {
    var fileInput = uploadForm.querySelector("[data-upload-input]");
    var submitBtn = uploadForm.querySelector("[data-upload-submit]");
    var errorEl = uploadForm.querySelector("[data-upload-error]");
    var grid = document.querySelector("[data-bank-grid]");

    submitBtn.addEventListener("click", async function () {
      var files = Array.prototype.slice.call(fileInput.files || []);
      if (!files.length) return;
      submitBtn.disabled = true;
      errorEl.hidden = true;

      if (!grid) {
        grid = document.createElement("ul");
        grid.className = "memz-thumb-grid";
        grid.setAttribute("data-bank-grid", "");
        uploadForm.insertAdjacentElement("afterend", grid);
      }

      for (var i = 0; i < files.length; i++) {
        var body = new FormData();
        body.append("file", files[i]);
        try {
          var image = await window.memz.api("POST", "/memz/api/images/", body);
          var li = document.createElement("li");
          li.className = "memz-thumb memz-thumb--status";
          li.setAttribute("data-bank-row", image.id);
          li.innerHTML =
            '<img src="' + image.url + '" alt="">' +
            '<span class="memz-status-badge memz-status-badge--' + image.moderation_status + '">' +
            (STATUS_LABEL[image.moderation_status] || image.moderation_status) + "</span>" +
            '<button type="button" class="memz-btn memz-btn--ghost memz-btn--small memz-thumb-delete" data-delete-image="' + image.id + '">מחיקה</button>';
          grid.prepend(li);
          bumpCount("[data-bank-count]", 1);
          li.querySelector("[data-delete-image]").addEventListener("click", async function () {
            await window.memz.api("DELETE", "/memz/api/images/" + image.id + "/");
            li.remove();
            bumpCount("[data-bank-count]", -1);
          });
        } catch (e) {
          errorEl.textContent = (e.data && (e.data.file || e.data.detail)) || "העלאה נכשלה.";
          errorEl.hidden = false;
        }
      }
      fileInput.value = "";
      submitBtn.disabled = false;
    });
  }
})();
