// improv: the top keys of an 88-key piano as buttons. Pure: no browser, runs under Node in the tests.
// C8 (108) is a screen's primary action, B7 (107) the second, A#7 (106) the third. They act at
// note-on only, and the same key twice within DEBOUNCE_MS counts once.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovControl = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const KEYS = { 108: "primary", 107: "secondary", 106: "tertiary" };
  const NAMES = { primary: "C8", secondary: "B7", tertiary: "A#7" };
  const DEBOUNCE_MS = 400;

  function actionFor(note) {
    return Object.prototype.hasOwnProperty.call(KEYS, note) ? KEYS[note] : null;
  }

  function isControlNote(note) {
    return actionFor(note) !== null;
  }

  function keyName(action) {
    return NAMES[action] || "";
  }

  function createController() {
    const lastAt = {};
    function handle(message, timeMs) {
      if (!message || message.type !== "on") return null;
      const action = actionFor(message.note);
      if (!action) return null;
      if (lastAt[action] !== undefined && timeMs - lastAt[action] < DEBOUNCE_MS) return null;
      lastAt[action] = timeMs;
      return action;
    }
    return { handle };
  }

  // The first button of this action that is shown and enabled, or -1.
  function choose(buttons, action) {
    return buttons.findIndex((b) => b.action === action && !b.hidden && !b.disabled);
  }

  function legend() {
    return `${NAMES.primary} primary, ${NAMES.secondary} second, ${NAMES.tertiary} third`;
  }

  return { KEYS, DEBOUNCE_MS, actionFor, isControlNote, keyName, createController, choose, legend };
});
