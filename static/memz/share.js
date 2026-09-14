/* The share button (spec §8.2): shares the image file itself where the Web
   Share API allows files, falls back to sharing the URL, falls back to
   copying it. Also wires the "report" link (spec Rule 6.4.3). */
(function () {
  "use strict";

  document.querySelectorAll("[data-share-meme]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      var url = btn.dataset.shareUrl;
      var imageUrl = btn.dataset.shareImage;
      var title = "memz";
      var status = document.querySelector(btn.dataset.shareStatus || "");

      try {
        if (imageUrl && navigator.canShare) {
          var response = await fetch(imageUrl);
          var blob = await response.blob();
          var file = new File([blob], "memz.jpg", { type: blob.type || "image/jpeg" });
          if (navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], title: title, url: url });
            return;
          }
        }
        if (navigator.share) {
          await navigator.share({ title: title, url: url });
          return;
        }
      } catch (e) {
        // A cancelled share throws too; fall through to the copy fallback
        // only if nothing was shared and the API itself is unsupported.
        if (e && e.name === "AbortError") return;
      }

      try {
        await navigator.clipboard.writeText(url);
        if (status) status.textContent = "הקישור הועתק";
      } catch (e) {
        if (status) status.textContent = url;
      }
    });
  });

  document.querySelectorAll("[data-report-meme]").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      btn.disabled = true;
      var status = document.querySelector(btn.dataset.reportStatus || "");
      try {
        await window.memz.api("POST", "/memz/api/report/", { slug: btn.dataset.reportMeme });
        if (status) status.textContent = "תודה, נבדוק";
      } catch (e) {
        if (status) status.textContent = "לא הצלחנו לשלוח, נסו שוב";
        btn.disabled = false;
      }
    });
  });
})();
