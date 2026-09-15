(function () {
  "use strict";
  var form = document.querySelector("[data-join-form]");
  if (!form) return;

  var codeInput = form.querySelector("[data-join-code]");
  var nicknameInput = form.querySelector("[data-join-nickname]");
  var submitBtn = form.querySelector("[data-join-submit]");
  var errorEl = form.querySelector("[data-join-error]");

  codeInput.addEventListener("input", function () {
    codeInput.value = codeInput.value.toUpperCase();
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var code = codeInput.value.trim().toUpperCase();
    if (!code) { codeInput.focus(); return; }
    submitBtn.disabled = true;
    errorEl.hidden = true;
    try {
      var data = await window.memz.api("POST", "/memz/api/sessions/" + encodeURIComponent(code) + "/join/", {
        nickname: nicknameInput.value,
      });
      window.memz.setPlayerToken(data.code, data.token);
      window.location.href = "/memz/s/" + data.code + "/";
    } catch (err) {
      errorEl.textContent = (err.data && err.data.detail) || "לא הצלחנו להצטרף, בדקו את הקוד.";
      errorEl.hidden = false;
      submitBtn.disabled = false;
    }
  });
})();
