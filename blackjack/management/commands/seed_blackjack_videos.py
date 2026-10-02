"""Put the first videos on the learning screen, once.

    manage.py seed_blackjack_videos

Adds the videos that are missing, by YouTube id, and touches nothing that
exists. A row root has reworded, reordered or switched off stays exactly as
root left it, which is the methodology's rule for every seed: a deploy never
rewrites somebody's edit.

How these were chosen (2026-10-02): embeddable (checked against YouTube's
oEmbed), and the transcript of each was read to confirm it shows what the line
below says it shows. Two are from Blackjack Apprenticeship, which teaches for
a living; the two on hand signals are the ones that actually perform them, one
for a face-up table and one for a hand-held game. All are in English.
"""

from django.core.management.base import BaseCommand

from blackjack.models import Clip

VIDEOS = [
    {
        "youtube_id": "UXmbwvr3aKk",
        "title": "How to Play Blackjack: Learn from an Expert",
        "channel": "Blackjack Apprenticeship",
        "group": Clip.GAME,
        "seconds": 613,
        "order": 1,
        "why": "מכאן מתחילים: המטרה, ערכי הקלפים, איך מחלקים, ומה עושים בכל תור.",
    },
    {
        "youtube_id": "MQHtVmkTesQ",
        "title": "Winning Blackjack Basic Strategy",
        "channel": "Blackjack Apprenticeship",
        "group": Clip.GAME,
        "seconds": 274,
        "order": 2,
        "why": "מה זו אסטרטגיית בסיס ולמה לא מספיק ללמוד תשעים אחוז ממנה. זה בדיוק מה שהטבלה והתרגול כאן באים ללמד.",
    },
    {
        "youtube_id": "PljDuynF-j0",
        "title": "How to Play (and Win) at Blackjack: The Expert's Guide",
        "channel": "Blackjack Apprenticeship",
        "group": Clip.GAME,
        "seconds": 881,
        "order": 3,
        "why": "אותו נושא באריכות: שני שחקנים מקצועיים מסבירים את המטרה ואת המשחק. למי שרוצה להעמיק.",
    },
    {
        "youtube_id": "sKQLqqyhGtI",
        "title": "Blackjack Hand Signals",
        "channel": "DarkStar Blackjack",
        "group": Clip.GESTURES,
        "seconds": 192,
        "order": 1,
        "why": "שולחן עם קלפים גלויים, ורוב השולחנות כאלה: טפיחה על השולחן לקלף, גל של היד מעל הקלפים לעצירה, ושבבים ליד ההימור להכפלה ולפיצול.",
    },
    {
        "youtube_id": "W9CQSjhbKVU",
        "title": "Hand gestures in hand-held blackjack",
        "channel": "Platypus Garden",
        "group": Clip.GESTURES,
        "seconds": 307,
        "order": 2,
        "why": "משחק שבו הקלפים ביד: מגרדים אותם קלות על השולחן לקלף, תוחבים אותם מתחת לשבבים לעצירה, ומפנים אותם כלפי מעלה להכפלה ולפיצול.",
    },
]


class Command(BaseCommand):
    help = "Add the starter videos to the learning screen, if they are missing."

    def handle(self, *args, **options):
        added = 0
        for row in VIDEOS:
            _clip, made = Clip.objects.get_or_create(
                youtube_id=row["youtube_id"],
                defaults={key: value for key, value in row.items() if key != "youtube_id"},
            )
            added += made
        self.stdout.write(
            f"videos: {added} added, {len(VIDEOS) - added} already there and left alone."
        )
