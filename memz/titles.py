"""Podium titles (spec §9.2): computed at the end of a game from votes,
submissions and timestamps, shown on the podium, one per player, best
first. Never stored (Rule 9.2.1) — a remembered session shows the same
titles when reopened because they are recomputed from the same rows, not
because anything was written down the first time.

"No two players the same title where the numbers allow" reads literally
here: `TITLE_ORDER` is the priority (best first, the spec table's own
order), assignment goes title by title down that list, each going to the
best-scoring player who does not already carry one. A title nobody
qualifies for (no judge mode, nobody unanimous, only one round played)
is simply not given to anyone rather than forced onto whoever is left —
that is what "where the numbers allow" is guarding against.
"""

from collections import Counter, defaultdict

from .models import Round, Session

CROWD_FAVOURITE = "crowd_favourite"
UNANIMOUS = "unanimous"
STREAK = "streak"
CLUTCH = "clutch"
SPEED = "speed"
DARK_HORSE = "dark_horse"
PHILOSOPHER = "philosopher"
MINIMALIST = "minimalist"
THE_CROWD = "the_crowd"
JUDGES_FAVOURITE = "judges_favourite"

# Best first — spec §9.2's own table order.
TITLE_ORDER = [
    CROWD_FAVOURITE, UNANIMOUS, STREAK, CLUTCH, SPEED,
    DARK_HORSE, PHILOSOPHER, MINIMALIST, THE_CROWD, JUDGES_FAVOURITE,
]

LABELS = {
    CROWD_FAVOURITE: "מלך/מלכת הערב",
    UNANIMOUS: "פה אחד",
    STREAK: "הרצף",
    CLUTCH: "ברגע האחרון",
    SPEED: "הזריז/ה",
    DARK_HORSE: "הסוס השחור",
    PHILOSOPHER: "הפילוסוף/ית",
    MINIMALIST: "המינימליסט/ית",
    THE_CROWD: "הקהל",
    JUDGES_FAVOURITE: "השופט/ת האהוב/ה",
}


def _round_winner_ids(points):
    """Submission ids tied for the top positive score — the same
    definition state.py's own `round_winner` flag uses, so "won a round"
    means one thing everywhere in this app."""
    top = max(points.values(), default=0)
    if top <= 0:
        return set()
    return {sid for sid, p in points.items() if p == top}


def _pick(metric, used, higher_is_better=True):
    candidates = {pid: v for pid, v in metric.items() if pid not in used}
    if not candidates:
        return None
    return max(candidates, key=candidates.get) if higher_is_better else min(candidates, key=candidates.get)


def _compute_metrics(session):
    """{title_key: {player_id: value}} — every title's raw, pre-assignment
    numbers (higher is always "more qualified" except `MINIMALIST`, where
    the value is an average caption length and shorter wins). Split out
    from `compute_titles` so each rule can be asserted directly, rather
    than only through which title a player ends up wearing after every
    higher-priority one has had first pick."""
    from .scoring import round_scores

    players = list(session.players.all())
    if not players:
        return {title: {} for title in TITLE_ORDER}
    player_ids = {p.id for p in players}
    rounds = list(session.rounds.filter(status=Round.DONE).order_by("number"))

    votes_received = Counter()
    unanimous = Counter()
    win_rounds_by_player = defaultdict(list)
    submitted_at_by_round = defaultdict(dict)
    caption_len_by_player = defaultdict(list)
    scored_caption_len_by_player = defaultdict(list)
    speed_first_count = Counter()
    crowd_agree_count = Counter()
    judge_pick_count = Counter()
    score_after_round = {}

    cumulative = Counter()
    for r in rounds:
        subs = list(r.submissions.filter(meme__isnull=False).select_related("player", "meme"))
        sub_by_id = {s.id: s for s in subs}
        points = round_scores(r)
        winner_sub_ids = _round_winner_ids(points)
        for sid in winner_sub_ids:
            win_rounds_by_player[sub_by_id[sid].player_id].append(r.number)

        votes = list(r.votes.all())
        if votes:
            counts = Counter(v.submission_id for v in votes)
            for sid, c in counts.items():
                votes_received[sub_by_id[sid].player_id] += c
                if session.scoring_mode == Session.VOTE and c == len(votes) and sid in winner_sub_ids:
                    unanimous[sub_by_id[sid].player_id] += 1
            if session.scoring_mode == Session.VOTE:
                for v in votes:
                    if v.submission_id in winner_sub_ids:
                        crowd_agree_count[v.voter_id] += 1
            elif session.scoring_mode == Session.JUDGE:
                pick = votes[0]
                judge_pick_count[sub_by_id[pick.submission_id].player_id] += 1

        if subs:
            timed = [s for s in subs if s.submitted_at]
            if timed:
                earliest = min(s.submitted_at for s in timed)
                for s in timed:
                    if s.submitted_at == earliest:
                        speed_first_count[s.player_id] += 1
                    submitted_at_by_round[r.number][s.player_id] = s.submitted_at

        for s in subs:
            length = len(s.meme.caption_text or "")
            caption_len_by_player[s.player_id].append(length)
            if points.get(s.id, 0) > 0:
                scored_caption_len_by_player[s.player_id].append(length)

        for sid, pts in points.items():
            cumulative[sub_by_id[sid].player_id] += pts
        score_after_round[r.number] = dict(cumulative)

    metrics = {CROWD_FAVOURITE: dict(votes_received), UNANIMOUS: dict(unanimous)}

    streak = Counter()
    for pid, won in win_rounds_by_player.items():
        won = sorted(won)
        best = run = 0
        prev = None
        for n in won:
            run = run + 1 if prev is not None and n == prev + 1 else 1
            best = max(best, run)
            prev = n
        if best >= 2:
            streak[pid] = best
    metrics[STREAK] = dict(streak)

    clutch = Counter()
    for r in rounds:
        if not r.caption_deadline:
            continue
        for pid in win_rounds_by_player:
            if r.number not in win_rounds_by_player[pid]:
                continue
            ts = submitted_at_by_round[r.number].get(pid)
            if ts and 0 <= (r.caption_deadline - ts).total_seconds() <= 5:
                clutch[pid] += 1
    metrics[CLUTCH] = dict(clutch)

    metrics[SPEED] = dict(speed_first_count)

    dark_horse = {}
    if len(rounds) >= 2:
        pre_index = len(rounds) - 3   # the round right before the last two started
        pre_scores = score_after_round.get(rounds[pre_index].number, {}) if pre_index >= 0 else {}
        final_scores = score_after_round[rounds[-1].number]
        for pid in player_ids:
            climb = final_scores.get(pid, 0) - pre_scores.get(pid, 0)
            if climb > 0:
                dark_horse[pid] = climb
    metrics[DARK_HORSE] = dark_horse

    metrics[PHILOSOPHER] = {
        pid: sum(lens) / len(lens) for pid, lens in caption_len_by_player.items() if lens
    }
    metrics[MINIMALIST] = {
        pid: sum(lens) / len(lens) for pid, lens in scored_caption_len_by_player.items() if lens
    }
    metrics[THE_CROWD] = dict(crowd_agree_count)
    metrics[JUDGES_FAVOURITE] = dict(judge_pick_count)
    return metrics


def compute_titles(session):
    """{player_id: title_key} for the players who earned one. A game with
    fewer done rounds/players than the pool has room for leaves some
    players without a title, by design (see module docstring)."""
    metrics = _compute_metrics(session)
    assigned = {}
    used = set()
    for title in TITLE_ORDER:
        higher_is_better = title != MINIMALIST
        pid = _pick(metrics[title], used, higher_is_better=higher_is_better)
        if pid is not None:
            assigned[pid] = title
            used.add(pid)
    return assigned
