// improv: the page layer for the control keys. Listens on every MIDI input, and when a control key
// goes down clicks the first shown, enabled button marked data-key-action for it. The rules live in
// control.js, which is tested under Node. It never touches the page's own MIDI handler: it adds a
// listener, so a screen that reads the piano keeps reading it.
(function () {
  const C = window.ImprovControl;
  if (!C || !navigator.requestMIDIAccess) return;

  const controller = C.createController();
  const attached = new WeakSet();

  function shown(el) {
    return el.getClientRects().length > 0;
  }

  function enabled(el) {
    return el.disabled !== true && el.getAttribute("aria-disabled") !== "true";
  }

  // A button marked data-key-action is a candidate itself. A list marked data-key-in offers its
  // first item (marked data-key-item) that is shown and enabled, so "the first lesson" and "the
  // latest take" are one key press away without marking each row.
  function candidates() {
    const out = [];
    for (const el of document.querySelectorAll("[data-key-action], [data-key-in]")) {
      if (el.dataset.keyAction) {
        out.push({ el, action: el.dataset.keyAction, hidden: !shown(el), disabled: !enabled(el) });
        continue;
      }
      const item = Array.from(el.querySelectorAll("[data-key-item]")).find((i) => shown(i) && enabled(i));
      out.push({ el: item || el, action: el.dataset.keyIn, hidden: !item, disabled: false });
    }
    return out;
  }

  // Only the button a key would press wears that key's name, so the hint is never a promise the
  // page cannot keep.
  const ACTIONS = ["primary", "secondary", "tertiary"];
  let scheduled = false;

  function refreshHints() {
    scheduled = false;
    for (const old of document.querySelectorAll("[data-key-hint]")) old.removeAttribute("data-key-hint");
    const list = candidates();
    for (const action of ACTIONS) {
      const at = C.choose(list, action);
      if (at >= 0) list[at].el.dataset.keyHint = C.keyName(action);
    }
  }

  function scheduleHints() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(refreshHints);
  }

  function press(action) {
    const list = candidates();
    const at = C.choose(list, action);
    if (at < 0) return;
    const el = list[at].el;
    el.classList.add("im-key-pressed");
    window.setTimeout(() => el.classList.remove("im-key-pressed"), 250);
    el.click();
  }

  function noteOn(data) {
    if (!data || data.length < 3 || (data[0] & 0xf0) !== 0x90 || data[1] > 127 || !(data[2] > 0 && data[2] < 128)) return null;
    return { type: "on", note: data[1], velocity: data[2] };
  }

  const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  // The last key the browser heard, so a key that does nothing can be told from a key that never arrived.
  function showHeard(note) {
    const el = document.getElementById("im-heard");
    if (el) el.textContent = `heard ${NAMES[note % 12]}${Math.floor(note / 12) - 1} (${note})`;
  }

  function onMessage(event) {
    const heard = noteOn(event.data);
    if (heard) showHeard(heard.note);
    const action = controller.handle(noteOn(event.data), event.timeStamp);
    if (action) press(action);
  }

  function attach(access) {
    for (const input of access.inputs.values()) {
      if (attached.has(input)) continue;
      attached.add(input);
      input.addEventListener("midimessage", onMessage);
      if (typeof input.open === "function") input.open().catch(() => {});
    }
  }

  new MutationObserver(scheduleHints).observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["hidden", "disabled", "style", "aria-disabled"],
  });
  scheduleHints();

  // Chrome stops delivering a port's messages once nothing holds its MIDIAccess, so this one is kept.
  navigator
    .requestMIDIAccess({ sysex: false })
    .then((access) => {
      window.__improvMidiAccess = access;
      attach(access);
      access.addEventListener("statechange", () => attach(access));
      document.documentElement.dataset.keys = "on";
    })
    .catch(() => {});
})();
