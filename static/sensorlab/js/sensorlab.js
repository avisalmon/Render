/* SensorLab's in-page toast, confirm and edit-in-place (SL-A4, spec §7.4).
 *
 * The app never calls the browser's `alert`, `confirm` or `prompt`. They
 * block the page, ignore the app's design, and on iOS announce the site's
 * own domain to the person using it. ustrip replaced 47 call sites for the
 * same reason and guards it with a real-browser test; SensorLab starts
 * with the helpers so there is never a call site to replace.
 *
 * Deliberately no framework and no build step: three functions and a small
 * amount of DOM.
 */
(function (window, document) {
  "use strict";

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function tray() {
    var found = document.querySelector(".sl-toast-tray");
    if (!found) {
      found = el("div", "sl-toast-tray");
      document.body.appendChild(found);
    }
    return found;
  }

  /** A short message that does not interrupt anything. */
  function toast(message, options) {
    var settings = options || {};
    var node = el("div", "sl-toast", message);
    node.setAttribute("role", "status");
    tray().appendChild(node);
    window.setTimeout(function () {
      node.remove();
    }, settings.ms || 3200);
    return node;
  }

  /**
   * An in-page confirm. Resolves true/false — never blocks the page.
   *
   * Returns a Promise so a caller reads like the native call it replaces:
   *   if (await sensorlab.confirm({title: "Delete this run?"})) { ... }
   */
  function confirm(options) {
    var settings = options || {};
    return new Promise(function (resolve) {
      var backdrop = el("div", "sl-backdrop");
      var dialog = el("div", "sl-dialog");
      dialog.setAttribute("role", "dialog");
      dialog.setAttribute("aria-modal", "true");

      dialog.appendChild(el("h2", null, settings.title || "Are you sure?"));
      if (settings.body) dialog.appendChild(el("p", null, settings.body));

      var actions = el("div", "sl-dialog-actions");
      var cancel = el("button", "sl-button sl-button-quiet", settings.cancelLabel || "Cancel");
      var ok = el(
        "button",
        "sl-button" + (settings.danger ? " sl-button-danger" : ""),
        settings.confirmLabel || "Confirm"
      );
      cancel.type = "button";
      ok.type = "button";
      actions.appendChild(cancel);
      actions.appendChild(ok);
      dialog.appendChild(actions);
      backdrop.appendChild(dialog);
      document.body.appendChild(backdrop);
      ok.focus();

      function close(answer) {
        backdrop.remove();
        document.removeEventListener("keydown", onKey);
        resolve(answer);
      }
      function onKey(event) {
        if (event.key === "Escape") close(false);
      }

      cancel.addEventListener("click", function () { close(false); });
      ok.addEventListener("click", function () { close(true); });
      backdrop.addEventListener("click", function (event) {
        if (event.target === backdrop) close(false);
      });
      // Escape closes, but this listener must never swallow anything else.
      document.addEventListener("keydown", onKey);
    });
  }

  /**
   * Edit a value where it sits, rather than in a prompt box.
   *
   * `target` is the element showing the value; `onSave(value)` may return a
   * promise. The original text is restored if the person cancels.
   */
  function editInPlace(target, onSave, options) {
    var settings = options || {};
    if (target.dataset.slEditing === "1") return;
    target.dataset.slEditing = "1";

    var original = target.textContent.trim();
    var input = el("input", "sl-input");
    input.type = settings.type || "text";
    input.value = original;

    function restore(text) {
      input.replaceWith(target);
      target.textContent = text;
      delete target.dataset.slEditing;
    }

    input.addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); commit(); }
      if (event.key === "Escape") { event.preventDefault(); restore(original); }
    });
    input.addEventListener("blur", commit);

    function commit() {
      var value = input.value.trim();
      if (value === original) return restore(original);
      Promise.resolve(onSave(value)).then(
        function () { restore(value); },
        function () { restore(original); toast(settings.errorMessage || "That did not save."); }
      );
    }

    target.replaceWith(input);
    input.focus();
    input.select();
  }

  window.sensorlab = window.sensorlab || {};
  window.sensorlab.toast = toast;
  window.sensorlab.confirm = confirm;
  window.sensorlab.editInPlace = editInPlace;
})(window, document);
