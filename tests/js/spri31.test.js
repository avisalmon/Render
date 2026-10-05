// SPR-I.3.1 improv: choosing a MIDI input, remembering it, and surviving a hot-plug, plus the
// Setup screen's own field rules. The page is glue and is checked by the pytest wrapper and in
// a real browser; the rules are proved here.

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const root = path.join(__dirname, "..", "..");
const setup = require(path.join(root, "static", "improv", "setup.js"));

// A Web MIDI input port carries rather more than this; these are the fields we read.
const port = (id, name, state = "connected") => ({ id, name, state });

// --------------------------------------------------------------- listing the inputs

test("the inputs are listed by name, and one that is not connected says so", () => {
  const list = setup.inputChoices([port("a", "Clavinova"), port("b", "Old keyboard", "disconnected")]);
  assert.deepEqual(list.map((c) => c.id), ["a", "b"]);
  assert.deepEqual(list.map((c) => c.label), ["Clavinova", "Old keyboard (unplugged)"]);
  assert.deepEqual(list.map((c) => c.connected), [true, false]);
});

test("what is plugged in comes first, and the rest in alphabetical order", () => {
  const list = setup.inputChoices([
    port("z", "Zeta", "disconnected"),
    port("m", "Minilab"),
    port("c", "Clavinova"),
    port("a", "Alpha", "disconnected"),
  ]);
  assert.deepEqual(list.map((c) => c.name), ["Clavinova", "Minilab", "Alpha", "Zeta"]);
});

test("a port with no id is not offered, and junk in the list is ignored", () => {
  const list = setup.inputChoices([null, undefined, {}, port("", "Nameless id"), port("ok", "Real")]);
  assert.deepEqual(list.map((c) => c.name), ["Real"]);
  assert.deepEqual(setup.inputChoices(null), []);
});

test("a port the browser gives no name is still usable, named by its own id", () => {
  const list = setup.inputChoices([port("4a9f", "   "), { id: "b2", state: "connected" }]);
  assert.deepEqual(list.map((c) => c.name), ["Input 4a9f", "Input b2"]);
});

// ------------------------------------------------------------- remembering the input

test("the keyboard used last time is picked again by its name, whatever its id is now", () => {
  const list = setup.inputChoices([port("new-id-7", "Clavinova"), port("other", "Minilab")]);
  assert.equal(setup.pickInput(list, "Clavinova").id, "new-id-7");
});

test("with nothing remembered, or the remembered one gone, the first plugged-in keyboard is used", () => {
  const list = setup.inputChoices([port("a", "Clavinova"), port("b", "Minilab")]);
  assert.equal(setup.pickInput(list, "").id, "a");
  assert.equal(setup.pickInput(list, "Gone keyboard").id, "a");
  assert.equal(setup.pickInput([], "Clavinova"), null);
});

test("an unplugged port is never picked, even when it is the one remembered", () => {
  const list = setup.inputChoices([port("a", "Clavinova", "disconnected"), port("b", "Minilab")]);
  assert.equal(setup.pickInput(list, "Clavinova").name, "Minilab");
  assert.equal(setup.pickInput(setup.inputChoices([port("a", "Clavinova", "disconnected")]), "Clavinova"), null);
});

test("two keyboards of the same name do not confuse it", () => {
  const list = setup.inputChoices([port("one", "Clavinova"), port("two", "Clavinova")]);
  assert.equal(setup.pickInput(list, "Clavinova").id, "one");
});

// ----------------------------------------------------------------------- hot-plugging

test("the first time the keyboards are listed, nothing about them is news", () => {
  const first = setup.inputChoices([port("a", "Clavinova"), port("b", "Minilab")]);
  assert.deepEqual(setup.changes(null, first), { added: [], removed: [] });
  assert.equal(setup.describeChange(setup.changes(null, first), "Clavinova"), "");
});

test("plugging a keyboard in and pulling it out is noticed by name", () => {
  const before = setup.inputChoices([port("a", "Clavinova")]);
  const after = setup.inputChoices([port("b", "Minilab")]);
  assert.deepEqual(setup.changes(before, after), { added: ["Minilab"], removed: ["Clavinova"] });
  assert.deepEqual(setup.changes(before, before), { added: [], removed: [] });
});

test("a port that merely goes quiet counts as unplugged, because it can no longer be played", () => {
  const before = setup.inputChoices([port("a", "Clavinova")]);
  const after = setup.inputChoices([port("a", "Clavinova", "disconnected")]);
  assert.deepEqual(setup.changes(before, after), { added: [], removed: ["Clavinova"] });
});

test("losing the keyboard being played is said plainly, and getting it back too", () => {
  const gone = { added: [], removed: ["Clavinova"] };
  assert.equal(setup.describeChange(gone, "Clavinova"), "Clavinova was unplugged. Plug it back in and it is picked up again.");
  assert.equal(setup.describeChange(gone, "Minilab"), "Clavinova was unplugged.");
  assert.equal(setup.describeChange({ added: ["Clavinova"], removed: [] }, ""), "Clavinova is connected.");
  assert.equal(setup.describeChange({ added: ["A", "B"], removed: [] }, ""), "A and B are connected.");
  assert.equal(setup.describeChange({ added: [], removed: [] }, "Clavinova"), "");
});

// --------------------------------------------------------------- the profile fields

test("a profile the player has not touched is accepted as it stands", () => {
  const clean = setup.cleanProfile(setup.BLANK_PROFILE);
  assert.deepEqual(clean.problems, {});
  assert.equal(clean.ok, true);
  assert.equal(clean.profile.daily_goal_minutes, 15);
  assert.equal(clean.profile.note_names, "sharps");
  assert.equal(clean.profile.demo_output, "piano");
  assert.equal(clean.profile.timezone, "Asia/Jerusalem");
  assert.equal(clean.profile.latency_offset_ms, 0);
});

test("a daily goal has to be a number of minutes somebody could actually practise", () => {
  for (const bad of ["", "   ", "abc", "0", "4", "241", "-10", "20.5"]) {
    assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, daily_goal_minutes: bad }).ok, false, `${bad} was accepted`);
  }
  const clean = setup.cleanProfile({ ...setup.BLANK_PROFILE, daily_goal_minutes: " 30 " });
  assert.equal(clean.ok, true);
  assert.equal(clean.profile.daily_goal_minutes, 30);
  assert.match(setup.cleanProfile({ ...setup.BLANK_PROFILE, daily_goal_minutes: "999" }).problems.daily_goal_minutes, /5 and 240/);
});

test("the choices are the choices, and nothing else gets stored", () => {
  assert.deepEqual(setup.NOTE_NAME_CHOICES.map((c) => c[0]), ["sharps", "flats"]);
  assert.deepEqual(setup.DEMO_OUTPUT_CHOICES.map((c) => c[0]), ["piano", "laptop"]);
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, note_names: "squiggles" }).ok, false);
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, demo_output: "trumpet" }).ok, false);
});

test("a timezone is needed, because a streak is made of the player's own days", () => {
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, timezone: "" }).ok, false);
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, timezone: "Europe/Berlin" }).ok, true);
});

test("the calibration number is left alone by the Setup screen but is still range checked", () => {
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, latency_offset_ms: "-48" }).profile.latency_offset_ms, -48);
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, latency_offset_ms: "5000" }).ok, false);
});

test("the keyboard's name is stored trimmed, and a silly long one cannot be stored at all", () => {
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, midi_input_name: "  Clavinova  " }).profile.midi_input_name, "Clavinova");
  assert.equal(setup.cleanProfile({ ...setup.BLANK_PROFILE, midi_input_name: "x".repeat(200) }).ok, false);
});

test("only the fields the server knows are sent, so a stray key cannot be smuggled in", () => {
  const body = setup.toBody({ ...setup.BLANK_PROFILE, id: 7, user: "someone", is_superuser: true, nonsense: 1 });
  assert.deepEqual(Object.keys(body).sort(), [...setup.FIELDS].sort());
});

test("nothing is sent when nothing was changed", () => {
  const saved = setup.cleanProfile(setup.BLANK_PROFILE).profile;
  assert.equal(setup.isDirty(saved, saved), false);
  assert.equal(setup.isDirty({ ...saved, daily_goal_minutes: 20 }, saved), true);
  assert.equal(setup.isDirty({ ...saved, midi_input_name: "Clavinova" }, saved), true);
});

// ------------------------------------------------------------------- sharps or flats

test("a note is spelled the way the player asked for it", () => {
  assert.equal(setup.spell(1, "sharps"), "C#");
  assert.equal(setup.spell(1, "flats"), "Db");
  assert.equal(setup.spell(0, "flats"), "C");
  assert.equal(setup.spell(60, "sharps"), "C", "a MIDI number is reduced to its pitch class");
  assert.equal(setup.spell(61, "flats"), "Db");
  assert.equal(setup.spell(1, "anything else"), "C#", "sharps are the fallback");
});
