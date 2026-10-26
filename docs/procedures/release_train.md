# The release train

**The one way anything on this site reaches production.** Avi, 2026-10-26:
"a lot of agents developing a lot of apps in parallel" on one repo, and
pushes were starting to collide. Code: [scripts/train.py](../../scripts/train.py).
Tests: [tests/test_release_train.py](../../tests/test_release_train.py).

## Why it exists

Five or more agents work on this repo at once: chats in VS Code sharing one
working tree (`C:\Projects\Render`), and the מט״צים mail bot in its own
clone. Before the train, any of them could push, and a push ships
everybody's commits. In the ten days before it was built:

- one chat's commit reached production in the middle of its own test run,
  pushed by another chat ([postmortems](../postmortems.md) PM-13);
- four apps' failures shipped unnoticed in other chats' pushes;
- a full regression took three hours because several ran at once and
  fought over the database and the ports;
- the counter app sat unregistered for three days (PM-26).

With one app and one developer none of this happens, and none of this is
needed. It is for many agents on many apps at once.

## The rules, for every agent

1. **Never `git push` to main.** A pre-push hook refuses it. Pushing a side
   branch is allowed (Render deploys only `main`).
2. **A commit means "ready to ship".** Commit only after your app's own tests
   pass (PM-13): any train may carry it.
3. **When Avi says push, deploy or publish: ship.**
   `.\env\Scripts\python.exe scripts\train.py ship --app <app> --run --wait 3600`
   from the shared tree. It prints the final record; report what it says.
4. **Don't run the full suite yourself.** Run your app's tests while you work;
   the full suite runs every night, once, for everybody.
5. **Read the board when you start**: `C:\Users\avisa\.claude\release-train\board.md`
   (or `scripts\train.py status`). It says what is waiting, what the last
   train and the last night found, whose failure is whose, and who is
   editing which shared file.
6. **Before editing a shared file** (`render.yaml`, `mysite/settings.py`,
   `mysite/urls.py`, `requirements*.txt`, `pyproject.toml`, `CLAUDE.md`):
   `scripts\train.py claim <path> --by <your app or chat> --why "<what>"`, and
   `release` it when you commit. A claim expires by itself after 30 minutes.
7. **A failure the train names as yours is yours to fix**, including one in
   another app that your change caused.

## What a train does

On `ship --run`, or on the next tick of the scheduled task:

1. Takes the lock (one train at a time; a second steps aside).
2. In its own clone (`C:\Projects\Render-train`, never the shared tree)
   builds a candidate: `origin/main`, plus the shared tree's `main`, plus any
   side branch a request named (the mail bot's). The clone's environment is
   derived from the shared tree by code, never by hand (PM-57): `setup` pins
   ruff to the shared tree's version, every ride runs `collectstatic`, and
   `mysite/settings_local.py` is rewritten from the shared tree's with every
   secret-shaped name (KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, PRIVATE), the
   Google provider block and every multi-line value left out. The clone owns
   nothing: it is hard-reset before every checkout, so never copy a file into
   it.
3. Works out what to test from the files the candidate changes:
   - an app's files (`<app>/`, `templates/<app>/`, `static/<app>/`) select
     every test file that names that app;
   - a test file selects itself;
   - **something every app shares** (`mysite/`, `app/`, `requirements*`,
     `render.yaml`, conftest, site-wide templates or static) runs **the full
     suite**, because for a shared file "the requester's tests" are
     everyone's;
   - documentation alone runs nothing;
   - anything else runs the **site contract**:
     [tests/train_contract.txt](../../tests/train_contract.txt).
4. Runs `manage.py check` and `makemigrations --check` (a forked migration is
   a cross-app break), then the selected tests, in parallel.
5. **Ships only if nothing new failed.** "New" means not in
   [tests/known_failures.txt](../../tests/known_failures.txt).
6. Pushes exactly what it tested, deletes the side branches it carried, and
   waits for Render's deployment of that commit (GitHub's deployment
   records).
7. If something failed: pushes nothing, names each new failure's app on the
   board, and mails Avi one short note ("רכבת: לא יצא ..."). **The mail bot's
   branch is then tried again alone**, so a break in the shared tree it never
   touched does not hold a client's request hostage.

## The night

Every night after 03:00, the first tick with nothing waiting runs the full
regression on what is live. It mails Avi only if something **new** failed
("רכבת: לילה: ..."), by app, and the board lists any known failure that
started passing, so its line can come out of the list.

## Known failures

`tests/known_failures.txt`: one line per test, with its owning app, the date
and why. It exists so the old failures stop hiding new ones. A line is a
debt with a name on it, not a decision: the owner fixes the test and removes
the line.

## Staying alive

The train lives on Avi's PC, which is meant to be always on. What keeps it
going, and what watches it:

| Piece | How |
|---|---|
| Scheduled task `release-train` | Every 10 minutes and at logon; runs a missed run as soon as it can; never two at once; restarts up to 3 times if it fails |
| Scheduled task `matazim-mail` | The same, and now also at logon |
| The published train runs, not the edited one | `tick.ps1` copies `scripts/train.py` from the train's own clone (= main) before each tick |
| A dead or hung train | The lock carries a heartbeat; a lock with no process, no heartbeat for 10 minutes, or past its time limit is broken by the next tick, the process tree killed and its requests put back in the queue |
| A stuck test run | Every pytest run has a time limit (45 minutes; 135 for the full suite; 5 hours at night) and is killed past it |
| The bot goes silent | Every tick checks the bot's heartbeat (`matazim-mail\last-check.txt`); 40 minutes silent, or a lock over 3 hours old, mails Avi |
| The train goes silent | The bot checks the train's heartbeat (`release-train\last-tick.txt`) on every run; 40 minutes silent mails Avi |
| A night missed | Alert if the last nightly is over 30 hours old |
| A task removed or disabled | Every tick checks both tasks exist and are enabled |
| Alert spam | Each alert is sent once, again only after 12 hours if still true, and cleared on the board when it stops |

**What it cannot survive by itself:** the PC off, or on but signed out. Both
tasks run only while Avi is signed in, like the mail bot always has. Two
settings close that gap, and only Avi can set them:

1. In Task Scheduler, for both tasks: *Run whether user is logged on or not*
   (it asks for the Windows password once).
2. Windows Update: set active hours, and turn on *notify before restarting*,
   so updates don't reboot it in the middle of the day.

## What the hook is, and is not

The pre-push hook stops accidents by cooperative agents, which is the
whole problem it was built for. It is not a lock: any agent can set the
override or push with `--no-verify`, and a line added to
`known_failures.txt` gets a failing test past the train. All of that is
visible in the diff and on the board, and the rules in CLAUDE.md forbid
it. The hard version, once the train has run for a while: a branch
protection rule on GitHub that lets only the train's own credential push
`main`, with the shared tree and the bot's clone on a read-only token.
Only Avi can set that up.

## When something is wrong

- **Look first:** `scripts\train.py status` and the logs in
  `C:\Users\avisa\.claude\release-train\logs`.
- **A train is stuck:** `scripts\train.py watchdog` breaks a dead or hung lock
  and requeues its work.
- **Production is on fire and the train is in the way:** Avi only,
  `$env:RELEASE_TRAIN_OVERRIDE = "1"; git push origin main`. Then a
  post-mortem.
- **Stop the train:** disable the `release-train` task. Requests wait; nothing
  is lost.

## Files

| Where | What |
|---|---|
| `scripts/train.py` | The train: `ship`, `run`, `nightly`, `tick`, `watchdog`, `status`, `claim`, `release`, `setup`, `hooks` |
| `scripts/hooks/pre-push` | Refuses pushes to main except the train's; then the FullStackBKM gate |
| `tests/train_contract.txt`, `tests/known_failures.txt` | What every train runs; what is known to fail |
| `C:\Users\avisa\.claude\release-train\` | The board (`board.md`, `state.json`), the lock, `tick.ps1`, the logs |
| `C:\Projects\Render-train\` | The train's own clone and environment |
