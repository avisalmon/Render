// improv: reading MIDI messages. Pure: no browser, runs under Node in the tests.
// Used: note on (velocity 0 is note off), note off, the sustain pedal. Channel is
// ignored. Everything else is dropped, including anything malformed.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovMidi = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

  function parse(data) {
    if (!data || data.length < 2) return null;
    const status = data[0];
    if (status >= 0xf0) return null; // system messages: clock, sysex, active sensing
    const kind = status & 0xf0;
    const a = data[1];
    const b = data.length > 2 ? data[2] : undefined;

    if (kind === 0x90 || kind === 0x80) {
      if (b === undefined || a > 127 || b > 127) return null;
      if (kind === 0x90 && b > 0) return { type: "on", note: a, velocity: b };
      return { type: "off", note: a };
    }
    if (kind === 0xb0 && a === 64 && b !== undefined && b <= 127) {
      return { type: "pedal", down: b >= 64 };
    }
    return null;
  }

  // The bytes to send a note out: the same message as comes in. A velocity of 0 to 1 is
  // scaled to MIDI's 0 to 127; anything larger is taken to be MIDI already.
  function noteOnBytes(note, velocity) {
    const v = velocity <= 1 ? Math.round(velocity * 127) : Math.round(velocity);
    return Uint8Array.from([0x90, note & 0x7f, Math.min(127, Math.max(1, v))]);
  }

  function noteOffBytes(note) {
    return Uint8Array.from([0x80, note & 0x7f, 0]);
  }

  // Middle C (60) is C4.
  function noteName(note) {
    return NAMES[note % 12] + (Math.floor(note / 12) - 1);
  }

  return { parse, noteName, noteOnBytes, noteOffBytes };
});
