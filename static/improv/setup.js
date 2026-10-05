// improv: the rules behind the Setup screen. Pure: no browser, runs under Node in the tests.
//
// Two jobs. First, which MIDI input to listen to: the keyboard is remembered by its *name*,
// because a port's id is not promised to be the same between sessions while the name is what
// the player recognises. Second, the profile fields, checked here so the screen can say what
// is wrong before the server does.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.ImprovSetup = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"];

  const NOTE_NAME_CHOICES = [["sharps", "Sharps (C#)"], ["flats", "Flats (Db)"]];
  const DEMO_OUTPUT_CHOICES = [["piano", "The piano, over MIDI"], ["laptop", "The laptop, as a plain tone"]];
  const GOAL_MIN = 5;
  const GOAL_MAX = 240;
  const OFFSET_LIMIT_MS = 500;
  const NAME_LIMIT = 120;
  const FIELDS = ["daily_goal_minutes", "latency_offset_ms", "midi_input_name", "note_names", "demo_output", "timezone"];

  const BLANK_PROFILE = {
    daily_goal_minutes: 15,
    latency_offset_ms: 0,
    midi_input_name: "",
    note_names: "sharps",
    demo_output: "piano",
    timezone: "Asia/Jerusalem",
  };

  // ------------------------------------------------------------------ the inputs

  function inputChoices(ports) {
    const list = [];
    for (const port of ports || []) {
      if (!port || typeof port.id !== "string" || port.id === "") continue;
      const given = typeof port.name === "string" ? port.name.trim() : "";
      const connected = port.state !== "disconnected";
      list.push({
        id: port.id,
        name: given || `Input ${port.id}`,
        label: given || `Input ${port.id}`,
        connected,
      });
    }
    list.sort((a, b) => (a.connected === b.connected ? a.name.localeCompare(b.name) : a.connected ? -1 : 1));
    for (const choice of list) if (!choice.connected) choice.label = `${choice.name} (unplugged)`;
    return list;
  }

  function pickInput(choices, rememberedName) {
    const usable = (choices || []).filter((c) => c.connected);
    const remembered = usable.find((c) => c.name === rememberedName);
    return remembered || usable[0] || null;
  }

  // Where a demo goes when it goes to the piano: the output with the piano's own name, so
  // the sound comes out of the instrument the player is sitting at; else the first plugged in.
  function pickOutput(choices, inputName) {
    const usable = (choices || []).filter((c) => c.connected);
    return usable.find((c) => c.name === inputName) || usable[0] || null;
  }

  // What can be played changed: an unplugged port counts as gone, because it cannot be used.
  // The first listing has nothing to compare with, so nothing about it is news.
  function changes(before, after) {
    if (!before) return { added: [], removed: [] };
    const names = (list) => (list || []).filter((c) => c.connected).map((c) => c.name);
    const was = names(before);
    const now = names(after);
    return {
      added: now.filter((name) => !was.includes(name)),
      removed: was.filter((name) => !now.includes(name)),
    };
  }

  function listNames(names) {
    if (names.length === 1) return names[0];
    return names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
  }

  function describeChange(change, listeningName) {
    const parts = [];
    if (change.removed.length) {
      const lost = change.removed.includes(listeningName);
      parts.push(
        `${listNames(change.removed)} ${change.removed.length === 1 ? "was" : "were"} unplugged.` +
          (lost ? " Plug it back in and it is picked up again." : "")
      );
    }
    if (change.added.length) {
      parts.push(`${listNames(change.added)} ${change.added.length === 1 ? "is" : "are"} connected.`);
    }
    return parts.join(" ");
  }

  // ----------------------------------------------------------------- the profile

  function wholeNumber(value) {
    const text = String(value === undefined || value === null ? "" : value).trim();
    return /^-?\d+$/.test(text) ? Number(text) : null;
  }

  function cleanProfile(fields) {
    const given = fields || {};
    const profile = {};
    const problems = {};

    const goal = wholeNumber(given.daily_goal_minutes);
    if (goal === null) problems.daily_goal_minutes = "A daily goal is a whole number of minutes.";
    else if (goal < GOAL_MIN || goal > GOAL_MAX) problems.daily_goal_minutes = `A daily goal is between ${GOAL_MIN} and ${GOAL_MAX} minutes.`;
    else profile.daily_goal_minutes = goal;

    const offset = wholeNumber(given.latency_offset_ms);
    if (offset === null) problems.latency_offset_ms = "The calibration offset is a whole number of milliseconds.";
    else if (Math.abs(offset) > OFFSET_LIMIT_MS) problems.latency_offset_ms = `The calibration offset is within ${OFFSET_LIMIT_MS} ms either way.`;
    else profile.latency_offset_ms = offset;

    const name = String(given.midi_input_name === undefined || given.midi_input_name === null ? "" : given.midi_input_name).trim();
    if (name.length > NAME_LIMIT) problems.midi_input_name = "That keyboard's name is too long to store.";
    else profile.midi_input_name = name;

    for (const [field, choices] of [["note_names", NOTE_NAME_CHOICES], ["demo_output", DEMO_OUTPUT_CHOICES]]) {
      const value = String(given[field] === undefined || given[field] === null ? "" : given[field]);
      if (choices.some((c) => c[0] === value)) profile[field] = value;
      else problems[field] = "That is not one of the choices.";
    }

    const zone = String(given.timezone === undefined || given.timezone === null ? "" : given.timezone).trim();
    if (!zone) problems.timezone = "A timezone is needed, because a streak is made of your own days.";
    else profile.timezone = zone;

    return { ok: Object.keys(problems).length === 0, profile, problems };
  }

  function toBody(profile) {
    const body = {};
    for (const field of FIELDS) body[field] = profile[field];
    return body;
  }

  function isDirty(now, saved) {
    if (!saved) return true;
    return FIELDS.some((field) => String(now[field]) !== String(saved[field]));
  }

  function spell(note, style) {
    const names = style === "flats" ? FLAT : SHARP;
    return names[((note % 12) + 12) % 12];
  }

  return {
    NOTE_NAME_CHOICES,
    DEMO_OUTPUT_CHOICES,
    GOAL_MIN,
    GOAL_MAX,
    OFFSET_LIMIT_MS,
    NAME_LIMIT,
    FIELDS,
    BLANK_PROFILE,
    inputChoices,
    pickInput,
    pickOutput,
    changes,
    describeChange,
    cleanProfile,
    toBody,
    isDirty,
    spell,
  };
});
