/* memz — an image library screen (ACT-Z.18).

   Two screens are the same screen with different plumbing: a player's own
   bank (/memz/images/, quota, private) and the admin's public bank
   (/memz/bank/, unlimited, categorised). Rather than keep two copies of
   "upload, show, delete, keep the counter honest" in sync, both pages
   render the same markup and point this at their own endpoints through
   data attributes on the grid.

   Everything it does goes through the REST API and patches the DOM in
   place — never a reload after an action (spec Rule 11.1: a tap never
   costs you your place, and on this screen it would also cost you your
   scroll position halfway down a grid of photos). */
(function () {
  "use strict";

  var STATUS_LABEL = { approved: "אושרה", rejected: "נדחתה", pending: "בבדיקה" };

  var grid = document.querySelector("[data-library-grid]");
  var slot = document.querySelector("[data-library-uploader]");
  if (!grid || !slot || !window.memz.mountUploader) return;

  var uploadUrl = grid.dataset.uploadUrl;
  var deleteBase = grid.dataset.deleteBase;
  var packInput = document.querySelector("[data-library-pack]");
  var counter = document.querySelector("[data-library-count]");
  var emptyNote = document.querySelector("[data-library-empty]");

  // "(3/30)" on the heading, kept in step with what is actually on screen
  // so the number never disagrees with the pictures under it.
  function bumpCount(delta) {
    if (!counter) return;
    var m = counter.textContent.match(/\((\d+)\/(\d+|∞)\)/);
    if (!m) return;
    var next = Math.max(0, parseInt(m[1], 10) + delta);
    counter.textContent = counter.textContent.replace(m[0], "(" + next + "/" + m[2] + ")");
  }

  function wireDelete(button) {
    button.addEventListener("click", async function () {
      button.disabled = true;
      try {
        await window.memz.api("DELETE", deleteBase + button.dataset.libraryDelete + "/");
        var row = button.closest("[data-library-row]");
        if (row) row.remove();
        bumpCount(-1);
        if (emptyNote && !grid.querySelector("[data-library-row]")) emptyNote.hidden = false;
      } catch (e) {
        button.disabled = false;
      }
    });
  }

  grid.querySelectorAll("[data-library-delete]").forEach(wireDelete);

  window.memz.mountUploader(slot, {
    label: slot.dataset.uploaderLabel || "הוספת תמונות משלכם",
    endpoint: uploadUrl,
    fields: packInput ? function () { return { pack: packInput.value || "" }; } : null,
    onUploaded: function (image) {
      if (emptyNote) emptyNote.hidden = true;
      var li = document.createElement("li");
      li.className = "memz-thumb memz-thumb--status";
      li.setAttribute("data-library-row", image.id);
      li.innerHTML =
        '<img src="' + image.url + '" alt="">' +
        '<span class="memz-status-badge memz-status-badge--' + image.moderation_status + '">' +
        (STATUS_LABEL[image.moderation_status] || image.moderation_status) + "</span>" +
        '<button type="button" class="memz-btn memz-btn--ghost memz-btn--small memz-thumb-delete" ' +
        'data-library-delete="' + image.id + '">מחיקה</button>';
      grid.prepend(li);
      bumpCount(1);
      wireDelete(li.querySelector("[data-library-delete]"));
    },
  });
})();
