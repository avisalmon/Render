/* memz — the public bank's uploader (ACT-Z.17), staff only.

   The same camera/gallery control every other screen uses
   (window.memz.mountUploader), pointed at the bank endpoint and carrying
   the chosen category with each file. Everything it uploads becomes part
   of the general bank, so the one thing this screen adds over the
   profile's is that the category travels with the upload. */
(function () {
  "use strict";

  var STATUS_LABEL = { approved: "אושרה", rejected: "נדחתה", pending: "בבדיקה" };

  var slot = document.querySelector("[data-bank-uploader]");
  var packInput = document.querySelector("[data-bank-pack]");
  var grid = document.querySelector("[data-bank-grid]");
  if (!slot || !window.memz.mountUploader) return;

  function wireDelete(button) {
    button.addEventListener("click", async function () {
      button.disabled = true;
      try {
        await window.memz.api("DELETE", "/memz/api/bank/images/" + button.dataset.bankDelete + "/");
        var row = button.closest("[data-bank-row]");
        if (row) row.remove();
      } catch (e) {
        button.disabled = false;
      }
    });
  }

  document.querySelectorAll("[data-bank-delete]").forEach(wireDelete);

  window.memz.mountUploader(slot, {
    label: "העלאה לבנק",
    endpoint: "/memz/api/bank/images/",
    fields: function () {
      return { pack: (packInput && packInput.value) || "" };
    },
    onUploaded: function (image) {
      if (!grid) return;
      var empty = grid.querySelector(".memz-fineprint");
      if (empty) empty.remove();
      var li = document.createElement("li");
      li.className = "memz-thumb memz-thumb--status";
      li.setAttribute("data-bank-row", image.id);
      li.innerHTML =
        '<img src="' + image.url + '" alt="">' +
        '<span class="memz-status-badge memz-status-badge--' + image.moderation_status + '">' +
        (STATUS_LABEL[image.moderation_status] || image.moderation_status) + "</span>" +
        '<button type="button" class="memz-btn memz-btn--ghost memz-btn--small memz-thumb-delete" ' +
        'data-bank-delete="' + image.id + '">מחיקה</button>';
      grid.prepend(li);
      wireDelete(li.querySelector("[data-bank-delete]"));
    },
  });
})();
