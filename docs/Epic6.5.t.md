CrashTech — Hackathon Platform Specification
A web application module inside an existing host system
Version 0.1 (draft) · Prepared for build hand-off

1. Overview
CrashTech is a web-based hackathon platform delivered as an app inside an existing host system. It does not manage its own user registration — all users already exist in (or enter through) the host system, and CrashTech grants them roles on specific hackathons.
A CrashTech hackathon is a hardware-centric, timed competition. Teams receive physical equipment (e.g. ESP32, FPGA) two weeks ahead, prepare using example code and tutorials, then compete during a fixed event window (default 24 h) to solve secret challenges for points. Submissions (a short video demo + source code) are reviewed by judges. The event ends with a permanent, public Glory Page memorializing the event.
Event lifecycle
SETUP  ──►  READINESS (≈2 weeks)  ──►  LIVE EVENT (≈24 h)  ──►  CLOSED  ──►  GLORY (permanent)
PhaseWho actsWhat happensSetupOrganizer, AdminCreate hackathon, define challenges (hidden), set team size & hardware stock, link GitHub repo, assign judgesReadinessOrganizer, Admin, ParticipantsInvite participants, form & name teams, ship & track hardware, participants practice with repo + example solutionsLive eventTeams, Judges, OrganizerChallenges unlock at kickoff; teams pick, build, submit; judges approve points; organizer awards bonuses; live anonymized leaderboardClosedSystemGates close at deadline; no further submissions acceptedGloryOrganizer, everyoneCertificates issued; permanent public memorial page with consented videos & photos

2. Roles & permissions
Roles are assigned per hackathon (many-to-many). One person may organize one event, judge another, and compete in a third. A person may hold multiple roles on the same event (e.g. organizer who also judges) — though organizer-only powers (bonus points) remain gated to the organizer role.
CapabilityOrganizerAdminJudgeParticipant (Team)Create / configure hackathon✅———Define & edit challenges✅———Invite participants✅✅——Create / name teams, assign members✅✅——Track / mark hardware supplied✅✅——Assign judges✅———Review submissions, award pass/fail points✅—✅—Award performance/creativity bonus points✅———Pick challenges & submit solutions———✅View own team dashboard———✅View public leaderboard & video gallery✅✅✅✅

3. Functional requirements by phase
3.1 Setup phase

Organizer creates a hackathon: name, start datetime, duration / end datetime, team size, submission deadline, and the linked GitHub repository URL (holds example solutions, tutorials, starter code, required skills).
Organizer defines hardware stock — the quantity of hardware kits available. This caps the number of teams.
Organizer defines challenges (see §4). Challenges are secret (visible = false) until kickoff.
Organizer assigns judges (must be existing system users).

3.2 Readiness phase (≈2 weeks before)

Organizer/Admin search the host system for users and invite them; invitees receive an email and join the hackathon.
Organizer/Admin form teams, assign names, and place participants into teams. Team size is bounded by the organizer's setting (1, 2, 3, …).
Hardware tracking: each team's hardware status moves pending → shipped → received. The organizer/admin marks hardware as supplied once physically delivered. The system decrements stock and blocks team creation beyond available stock.
Participants access the GitHub repo and example solutions to practice.
A countdown to event start is visible to all invited participants.

3.3 Live event phase (≈24 h)

At kickoff, all challenges become visible to participants on the Event Main Page.
A prominent countdown to deadline is shown everywhere during the event.
Teams pick challenges, build solutions, and submit: a video demo (≤20 s) + source code.
Each submission enters a pending queue.
Judges review code + video and approve/reject pass/fail challenges; only the organizer awards performance/creativity bonuses.
Resubmission is allowed: a rejected (or improvable) submission can be resubmitted within the window; resubmission returns the challenge to pending. Rejections carry a feedback note so teams know why.
Points count only after approval. The leaderboard shows approved points plus a separate pending indicator per team.
At the deadline (24 h or organizer-defined), gates close — submissions are hard-blocked.

3.4 Glory phase (permanent)

Final leaderboard locked.
Certificates generated: participation for all; winner/runner-up documents for top teams.
Glory Page published — permanent, public memorial with consented challenge videos, event photos, final rankings, highlights.


4. Challenge model & scoring
Each challenge carries everything shown to participants when the event opens.
Challenge fields: id, hackathon_id, title, description (full brief), point_value, scoring_mode, top_submission_count, bonus_points_tiers[], visible, created_by, created_at.
Scoring modes

Pass/Fail (go / no-go). Team either completes the challenge or not; on approval they receive the fixed point_value. Judges or organizer may approve.
Performance / Creativity. In addition to (or instead of) base points, the organizer ranks the top N submissions (top_submission_count, e.g. 3–5) and awards bonus points per rank from bonus_points_tiers[]. Only the organizer can award these — judges cannot.


The race: teams compete simultaneously on total challenges solved (breadth) and on performance/creativity rankings (bonus tiers).


5. Leaderboard & visibility rules
SurfaceVisibilityPublic leaderboardAnonymized — "Team One, Team Two…" with approved points + pending points indicator. No names, no per-challenge detail.Team dashboard (private)Full detail for the team's own submissions, statuses, points, pending approvals, rejection feedback.Public video galleryAnonymized solution-demo videos — a showcase with no team attribution.Glory PagePermanent public archive; only consented videos/photos appear. (Winner de-anonymization is an organizer decision — see §9.)

6. Video & code submission
Video — multiple low-friction options:

Paste a YouTube link, or
Scan a QR code generated per team, per challenge (personal & authenticated, so the upload binds to the right team/challenge), opening a phone form to capture & upload video directly.
(Open to additional easy upload methods.)

Source code — uploaded with each submission. Recommended (decision to confirm): given the GitHub-centric workflow, accept a GitHub repo / PR / commit URL rather than (or in addition to) a file upload, tying submissions to the hackathon repo.

7. Pages & views inventory
Organizer

Hackathon setup form (name, dates, duration, team size, deadline, GitHub repo URL, hardware stock)
Challenge create/edit form (title, description, point value, scoring mode, top-N count, bonus tiers, visibility)
Participant search & invite page
Team management (create, name, assign members; hardware status)
Judge assignment page
Hardware inventory & tracking view (stock, shipped, received)
Submission review queue (video + code, approve/reject + feedback, award pass/fail points)
Bonus award page (rank top-N per performance/creativity challenge, assign bonus tiers)
Organizer leaderboard view (full, de-anonymized)
Certificate generation / issue page
Glory Page editor (curate photos, highlights, publish)

Admin

Participant management
Team creation & naming
Hardware tracking

Judge

Assigned-submissions queue (filter by challenge)
Submission detail (video + code) with approve/reject + feedback note

Participant / Team

Event main page (live hub: countdown, challenge list, team status)
Challenge list & challenge detail view (unlocked at kickoff)
Submission form (video via YouTube link or QR scan; source code / repo link)
Team dashboard (own submissions, statuses, points, pending, rejection feedback)
Consent screen (glory-page publication)

Public

Anonymized leaderboard (approved + pending)
Anonymized video gallery
Glory Page (permanent memorial)

Global / shared

Countdown component (to-start and in-event-to-deadline)
Notifications (event starting, challenges unlocked, submission approved/rejected, deadline approaching)


8. Data models

CrashTech references existing host-system users; it does not own auth/registration. Role is a per-hackathon join, so users can hold different roles across events.

User (referenced from host system) — id, name, email (read from host).
Hackathon — id, name, start_date, end_date, duration, team_size, organizer_id, github_repo_url, hardware_stock, status (setup | readiness | active | closed | glory), created_at.
Role — id, hackathon_id, user_id, role (organizer | admin | judge | participant). (many-to-many; multiple per user per hackathon allowed)
Team — id, hackathon_id, name, members[] (user_ids), hardware_status (pending | shipped | received), glory_consent (bool), created_at.
Challenge — id, hackathon_id, title, description, point_value, scoring_mode (pass_fail | performance_creativity), top_submission_count, bonus_points_tiers[], visible, created_by, created_at.
Submission — id, challenge_id, team_id, video_url, source_code_url, status (pending | approved | rejected), points_awarded, bonus_points_awarded, feedback_note, submitted_at, reviewed_by, reviewed_at. (resubmission resets status → pending)
QRToken — id, team_id, challenge_id, token, expires_at. (per team, per challenge; authenticated upload binding)
Certificate — id, hackathon_id, team_id, type (participation | winner | runner_up), generated_at, download_url.
GloryPage — id, hackathon_id, published (bool), photos[], highlights, videos[] (consented), final_rankings.
Leaderboard — derived view: per team, sum of approved points (+ bonus) and a separate sum of pending points, anonymized for public display.

9. Open decisions (defaults applied, please confirm)

Resubmission limit — default: unlimited resubmissions until the gate closes; each returns the challenge to pending. Confirm if you want a cap.
Pending-point anonymity — default: pending points are anonymized exactly like approved points (e.g. "Team Four: 120 approved · 30 pending"); no per-challenge leak.
Consent timing — default: collect glory-page consent up front at team setup (simple), with an optional post-event opt-out once teams see what would be published (safer). Confirm which.
Blind judging — default: submissions anonymized to judges as well, to reduce bias; organizer sees identities for bonus ranking. Confirm.
Source-code channel — default recommendation: GitHub repo/PR URL as the submission code field, tying into the hackathon repo. Confirm vs. file upload.
Tie-breaking — default: (1) most challenges solved, then (2) earliest final qualifying submission, then (3) most bonus placements. Confirm priority.
Winner de-anonymization on Glory Page — default: winners revealed, others remain anonymous unless consented. Confirm.


10. Completeness check
The system as specified covers the full hackathon lifecycle end-to-end: onboarding (via host system), team formation, hardware logistics with stock limits, secret timed challenges, dual scoring (pass/fail + performance/creativity), low-friction submission, judged approval with resubmission, a live anonymized race with pending visibility, hard deadline enforcement, recognition/certificates, and a permanent memorial. The remaining items in §9 are policy decisions, not missing features — the architecture supports any choice on each.