"""Basic strategy: what the correct play is, and why.

**This module is the only thing in the app that decides a correct play.** The
cheat sheet, the drill and the coaching all read what it produced. A language
model is never asked, because basic strategy is deterministic and a tutor that
is right 97 percent of the time teaches a wrong play once an hour to somebody
who cannot tell which time (spec 1.4).

**The reason travels with the decision.** Each rule below carries the sentence
that explains it, so the explanation a learner reads is attached to the logic
that produced their answer rather than written separately and drifting from it.
That is the same reason the chart and the drill share rows: a teaching product
whose explanation disagrees with its answer is worse than one that says nothing.

**What is not supported is refused, not approximated** (REQ-B.2.5). The chart
is a function of the rules, and serving a near-enough chart for a rule set
nobody encoded is how a trainer teaches a play that loses money. `supports()`
is the whole list, and it is deliberately short.

Actions: H hit, S stand, D double, P split. `fallback` is what to do when the
action is not available at the moment, which is a real case: a double is not
allowed on three cards, a split is not allowed once you are out of hands. D on
hard 9 falls back to hitting; D on soft 18 falls back to **standing**. Same
letter, opposite fallback, which is the ambiguity four letters cannot carry.
"""

HIT, STAND, DOUBLE, SPLIT = "H", "S", "D", "P"

HARD, SOFT, PAIR = "hard", "soft", "pair"

# Dealer upcards, with 11 standing for an ace.
DEALER_CARDS = tuple(range(2, 12))

HARD_TOTALS = tuple(range(5, 21))      # 21 is never a decision
SOFT_TOTALS = tuple(range(13, 21))     # A,2 through A,9
PAIR_RANKS = tuple(range(2, 12))       # 2..10, and 11 for aces

WEAK = (2, 3, 4, 5, 6)                 # the dealer busts often
STRONG = (7, 8, 9, 10, 11)

# Bumped whenever a rule or a reason changes. The seed command compares it to
# what a stored chart was built from and rebuilds when they differ, so a fix
# here reaches production without somebody remembering to type --rebuild.
# Cells are never edited by a person, which is what makes that safe.
STRATEGY_VERSION = 2


def face(dealer):
    """The dealer's card as a person says it. 11 is how the code counts an
    ace; nobody at a table has ever said "against eleven"."""
    return "אס" if dealer == 11 else str(dealer)


class Unsupported(Exception):
    """No chart exists for these rules, and we will not invent one."""


def supports(rules):
    """Whether a correct chart can be produced for this rule set.

    Short on purpose. Everything here is a combination whose chart is
    published and checkable; anything else refuses rather than guesses.

    Single and double deck are genuinely different charts, not the multi-deck
    chart with a smaller number on it, which is why they are out until
    somebody encodes them properly. Surrender adds a fifth action the product
    does not yet draw.
    """
    reasons = []
    if rules["decks"] not in (4, 6, 8):
        reasons.append("רק 4, 6 או 8 חפיסות בינתיים")
    if rules["surrender"] != "none":
        reasons.append("טבלה עם כניעה עוד לא נבנתה")
    if not rules["double_any_two"]:
        reasons.append("טבלה להכפלה על 9/10/11 בלבד עוד לא נבנתה")
    if not rules["dealer_peeks"]:
        reasons.append("טבלה לשולחן בלי הצצה עוד לא נבנתה")
    return (not reasons), reasons


def _hard(total, dealer, rules):
    """Hard totals: no ace, or an ace that must count as one."""
    h17 = rules["dealer_hits_soft_17"]

    if total >= 17:
        return STAND, STAND, (
            "17 ומעלה זו יד שכבר אי אפשר לשפר בלי להישרף ברוב המקרים. "
            "עוצרים, גם מול קלף חזק, כי לקיחת קלף כאן מפסידה יותר."
        )
    if total >= 13:
        if dealer in WEAK:
            return STAND, STAND, (
                f"מול {face(dealer)} לדילר יש סיכוי גבוה להישרף. אתם כבר ביד שנשרפת מקלף גבוה, "
                "אז נותנים לו לעבוד."
            )
        return HIT, HIT, (
            f"מול {face(dealer)} הדילר כנראה יגיע ל-17 ומעלה. {total} לא מנצח את זה, "
            "אז לוקחים קלף למרות הסיכון."
        )
    if total == 12:
        if dealer in (4, 5, 6):
            return STAND, STAND, (
                f"12 מול {face(dealer)} זה המקרה הכי לא אינטואיטיבי בטבלה. עוצרים לא כי היד טובה, "
                "אלא כי זה הקלף שהכי מפיל את הדילר."
            )
        return HIT, HIT, (
            f"12 מול {face(dealer)} עדיין מפסיד אם עוצרים. רק ארבעה קלפים מתוך שלושה-עשר שורפים אתכם כאן."
        )
    if total == 11:
        if dealer == 11 and not h17:
            return HIT, HIT, (
                "11 מול אס: כשהדילר עוצר על 17 רך, ההכפלה כאן כבר לא משתלמת. לוקחים קלף."
            )
        return DOUBLE, HIT, (
            "11 זו היד הכי טובה להכפלה: כל קלף בעל ערך עשר נותן 21, וזה קורה כמעט בשליש מהמקרים."
        )
    if total == 10:
        if dealer in (10, 11):
            return HIT, HIT, (
                f"10 מול {face(dealer)} לא מכפילים: הקלף של הדילר חזק מדי מכדי להכפיל את ההימור מולו."
            )
        return DOUBLE, HIT, (
            f"10 מול {face(dealer)} מכפילים: אתם מתחילים יותר גבוה ממנו, וקלף עשר נותן לכם 20."
        )
    if total == 9:
        if dealer in (3, 4, 5, 6):
            return DOUBLE, HIT, (
                f"9 מול {face(dealer)} זו הכפלה: הדילר חלש, ולכם יש יד שקלף אחד הופך לחזקה."
            )
        return HIT, HIT, "9 מול קלף שאינו חלש: פשוט לוקחים קלף, בלי להכפיל."
    return HIT, HIT, (
        "עם 8 ומטה אי אפשר להישרף מקלף אחד, אז לוקחים תמיד. אין כאן החלטה קשה."
    )


def _soft(total, dealer, rules):
    """Soft totals: an ace counting as eleven, so a card cannot bust you."""
    h17 = rules["dealer_hits_soft_17"]
    ace_with = total - 11          # A,2 is 13, so the partner is 2

    if total >= 20:
        return STAND, STAND, "A,9 זה 20. לא נוגעים."
    if total == 19:
        if h17 and dealer == 6:
            return DOUBLE, STAND, (
                "A,8 מול 6, בשולחן שבו הדילר לוקח על 17 רך, זו הכפלה צרה אבל נכונה."
            )
        return STAND, STAND, "A,8 זה 19, יד מנצחת. עוצרים."
    if total == 18:
        if dealer in (3, 4, 5, 6) or (h17 and dealer == 2):
            return DOUBLE, STAND, (
                f"A,7 מול {face(dealer)} מכפילים, ואם אי אפשר להכפיל, עוצרים. "
                "שימו לב: זה בדיוק התא שבו D ו-H מתבלבלים."
            )
        if dealer in (2, 7, 8):
            return STAND, STAND, (
                f"A,7 מול {face(dealer)} זה 18 מול יד בינונית. עוצרים ולא נוגעים."
            )
        return HIT, HIT, (
            f"A,7 מול {face(dealer)} זה המלכוד הקלאסי: 18 מרגיש כמו יד טובה, והוא מפסיד "
            "מול קלף חזק. לוקחים קלף, ואי אפשר להישרף."
        )
    if total == 17:
        if dealer in (3, 4, 5, 6):
            return DOUBLE, HIT, "A,6 מול דילר חלש: מכפילים."
        return HIT, HIT, "A,6 זו עדיין יד שצריך לשפר. לוקחים."
    if total in (15, 16):
        if dealer in (4, 5, 6):
            return DOUBLE, HIT, f"A,{ace_with} מול {face(dealer)}: מכפילים מול הקלפים החלשים ביותר."
        return HIT, HIT, f"A,{ace_with}: יד נמוכה, לוקחים קלף. האס מגן מפני שריפה."
    if dealer in (5, 6):
        return DOUBLE, HIT, f"A,{ace_with} מול {face(dealer)}: מכפילים רק מול 5 ו-6."
    return HIT, HIT, f"A,{ace_with}: לוקחים. אין מה להפסיד, האס סופג כל קלף."


def _pair(rank, dealer, rules):
    """Pairs: the question is whether two hands beat one."""
    das = rules["double_after_split"]

    if rank == 11:
        return SPLIT, HIT, (
            "אסים תמיד מפצלים. שני אסים זה 12 עלוב, ושתי ידיים שמתחילות מאס זה שתי הזדמנויות ל-21."
        )
    if rank == 10:
        return STAND, STAND, (
            "עשרות אף פעם לא מפצלים. 20 זו היד השנייה הכי טובה במשחק, "
            "ופיצול שלה מחליף יד מנצחת בשתי ידיים בינוניות."
        )
    if rank == 9:
        if dealer in (7, 10, 11):
            return STAND, STAND, (
                f"9,9 מול {face(dealer)} עוצרים: 18 מספיק טוב מול 7, ומול 10 או אס פיצול רק מכפיל הפסד."
            )
        return SPLIT, STAND, f"9,9 מול {face(dealer)} מפצלים: שתי ידיים שמתחילות ב-9 עדיפות על 18 אחד."
    if rank == 8:
        return SPLIT, HIT, (
            "שמיניות תמיד מפצלים. 16 היא היד הגרועה במשחק, ושתי ידיים שמתחילות ב-8 "
            "הן שיפור אפילו מול קלף חזק."
        )
    if rank == 7:
        if dealer in (2, 3, 4, 5, 6, 7):
            return SPLIT, HIT, f"7,7 מול {face(dealer)} מפצלים."
        return HIT, HIT, f"7,7 מול {face(dealer)} זה 14 מול קלף חזק. לוקחים קלף."
    if rank == 6:
        if dealer in (3, 4, 5, 6) or (das and dealer == 2):
            return SPLIT, HIT, (
                f"6,6 מול {face(dealer)} מפצלים, כי 12 זו יד שאי אפשר לעשות איתה כלום."
            )
        return HIT, HIT, f"6,6 מול {face(dealer)}: לא מפצלים מול קלף חזק, לוקחים קלף."
    if rank == 5:
        if dealer in (10, 11):
            return HIT, HIT, "5,5 זה 10, ואת 10 לא מפצלים לעולם. מול 10 או אס פשוט לוקחים."
        return DOUBLE, HIT, (
            "5,5 זה לא זוג, זה 10. מכפילים כמו כל 10, ולעולם לא מפצלים שתי חמישיות."
        )
    if rank == 4:
        if das and dealer in (5, 6):
            return SPLIT, HIT, "4,4 מפצלים רק מול 5 ו-6, וגם זה רק כשמותר להכפיל אחרי פיצול."
        return HIT, HIT, "4,4 זה 8, יד בטוחה לקלף נוסף. לא מפצלים."
    # 2,2 and 3,3
    if dealer in (4, 5, 6, 7) or (das and dealer in (2, 3)):
        return SPLIT, HIT, f"{rank},{rank} מול {face(dealer)} מפצלים."
    return HIT, HIT, f"{rank},{rank} מול {face(dealer)}: לא מפצלים, לוקחים קלף."


def decide(kind, player, dealer, rules):
    """The correct play, its fallback, and why. The whole module in one door."""
    ok, why = supports(rules)
    if not ok:
        raise Unsupported("; ".join(why))
    if kind == HARD:
        return _hard(player, dealer, rules)
    if kind == SOFT:
        return _soft(player, dealer, rules)
    if kind == PAIR:
        return _pair(player, dealer, rules)
    raise ValueError(f"no such kind of hand: {kind!r}")


def every_cell(rules):
    """Every decision basic strategy contains, for these rules.

    Yields `(kind, player, dealer, action, fallback, reason)`. This is what the
    chart is seeded from, and the count is whatever the game actually contains
    rather than a number quoted from somewhere.
    """
    for total in HARD_TOTALS:
        for dealer in DEALER_CARDS:
            yield (HARD, total, dealer, *decide(HARD, total, dealer, rules))
    for total in SOFT_TOTALS:
        for dealer in DEALER_CARDS:
            yield (SOFT, total, dealer, *decide(SOFT, total, dealer, rules))
    for rank in PAIR_RANKS:
        for dealer in DEALER_CARDS:
            yield (PAIR, rank, dealer, *decide(PAIR, rank, dealer, rules))
