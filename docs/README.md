# The documentation, and where each thing lives

Written 2026-09-21, when babook became a portal with apps around it and the
docs needed to say so. If you are looking for something and this file does not
name it, the file is in the wrong place rather than you looking in the wrong
place.

## babook itself

The main site: identity, the person's general profile, the training and
certification engine, and the portal.

| File | What it is |
|---|---|
| [main_spec.md](main_spec.md) | The spec. **Chapter 0 is the architecture**: what babook owns, what an app owns, and the directory of apps. |
| [backlog.md](backlog.md) | Epics, sprints and features, with status. |
| [dashboard.html](dashboard.html) | The progress view, **stale since 2026-05-27 and hand-maintained**. Read status from the backlog instead. Every app generates its dashboard from its own spec and backlog, with a test that fails when it drifts; babook needs the same and does not have it. |
| [regression.md](regression.md) | What the test suite covers, sprint by sprint. |
| [regression_baseline.txt](regression_baseline.txt) | The known-failing list. The gate is no *new* failures against it, because the suite has not been green in a long time and a rule nobody can follow is not a rule. |
| [architecture/](architecture/) | Design notes for babook's own surfaces: roles, onboarding, community. |
| [procedures/](procedures/) | Operational runbooks: email, backups, DNS, billing, video, deploys, env vars. How to *do* things, not what to build. |

## The apps

Each owns one topic completely and keeps its own spec, backlog, data model and
dashboard. Nothing about an app's behaviour belongs in babook's spec; §0.6
there is a directory and nothing more.

| App | Path | Docs |
|---|---|---|
| מט״צים | `/matazim/` | [matazim/](matazim/spec.md) |
| SensorLab | `/sensorlab/` | [sensorlab/](sensorlab/spec.md) |
| memz | `/memz/` | [memz/](memz/spec.md) |
| ustrip | `/ustrip/` | [ustrip/](ustrip/spec.md) |

Two capabilities are built but are not apps yet, both recorded in §0.6 of the
main spec: the home security relay at `/home/` (contract owned by the house
repo, see [security_relay_spec.md](security_relay_spec.md)) and CrashTech at
`/crashtech/` (spec at [Epic6.5.t.md](Epic6.5.t.md)).

## How we work

| File | What it is |
|---|---|
| [building_an_app.md](building_an_app.md) | **The authority for building anything new.** Six core rules and the kickoff sequence. Avi adds to it as we learn; re-read it rather than remembering it. |
| [the_manager.md](the_manager.md) | The delivery loop for the main site: spec to backlog to tests to build to regression. Still current; the Copilot-era framing in it is historical. |

## Course content

Course material and course-build plans, which are content rather than product:
[Phisics/](Phisics/) (pocket-physics) and
[transformers-academy-plan.md](transformers-academy-plan.md) (built in a
separate repo, tracked here).

## Archive

[archive/](archive/README.md) holds documents that are finished, answered or
superseded. They are kept because they carry reasoning somebody may need, and
they are out of the way because following them today would be wrong. Nothing in
the archive describes how the product works now.
