# Activation Metric & Onboarding Funnel (REQ-5.7)

How to measure the EPIC-5 first-time-user funnel in Plausible
(https://plausible.io → babook.co.il → Goals/Custom events).

## Funnel events (REQ-5.7.1)

| Event | Fired when | Where (code) |
|---|---|---|
| `entry` | First page of an anonymous session (`props.type` = home / course / lesson_locked / corporate / other) | `base.html` via `first_visit` context processor |
| `free_lesson_watched` | Anonymous visitor opens a free-preview lesson (`props.course`) | `lesson.html` |
| `wall_shown` | The /join/ registration wall renders (`props.course`) | `join.html` |
| `registered` | First load of /welcome/ after signup | `welcome.html` |
| `onboarding_started` | Same page load as `registered` | `welcome.html` |
| `onboarding_completed` | AI interview finishes or the static form submits | `welcome.html` |
| `first_lesson_completed` | A user's first-ever lesson reaches "complete" (localStorage-deduped per device) | `lesson.html` |
| `corporate_team_path` | Corporate visitor clicks the "for your team" learner path | `corporate.html` |

Set each of these up as a **Goal** in Plausible once (Site settings → Goals →
Add goal → Custom event).

## Activation rate (REQ-5.7.2)

**Activation = onboarding_completed AND first_lesson_completed, per registered.**

In Plausible, over the same period:

```
activation_rate = uniques(first_lesson_completed) / uniques(registered)
onboarding_rate = uniques(onboarding_completed) / uniques(registered)
wall_conversion = uniques(registered) / uniques(wall_shown)
```

Secondary funnel (anonymous → registered):

```
entry → free_lesson_watched → wall_shown → registered
```

Filter `entry` by `props.type=lesson_locked` to see the deep-link cohort -
the highest-intent arrivals (REQ-5.2.2).

## Caveats

- `first_lesson_completed` is deduped per device via localStorage
  (`babook_flc`), so cross-device users may double-count slightly.
- Events only fire in production (Plausible script loads only when
  `PLAUSIBLE_DOMAIN` is set, REQ-1.2.11).
- All events are anonymous counters - no PII leaves the site (REQ-5.2.4).
