"""Seed the public bank, decks and topics, once (spec §6.1, §12.7, §14.3;
building_an_app.md "Data").

Public packs and their images come from `memz/seed_assets/<pack-slug>/`,
keyed by `MemeImage.seed_key` (the file's relative path). The rule is
check-before-create: a key that already has a row is left alone, whatever
an admin did to that row since (title edited, image retired to `rejected`),
and nothing is ever deleted. Deleting a row makes the next run recreate it;
to take an image out of the public bank, retire it in the admin instead.

Caption decks and topics (SPR-Z.4) don't have a per-row key the way images
do, so the rule is coarser but the same in spirit: a deck or the topic pool
is seeded **only while it's empty**. The moment an admin has added, edited,
or removed a single card, this command leaves that deck alone forever —
never re-adds a removed card, never reintroduces one under a new id.

Runs on every deploy from render.yaml (from SPR-Z.7), like every `seed_*`
command in this repo, and is safe to run any number of times.

The images shipped in SPR-Z.1 are generated placeholders (see
`memz/seed_assets/make_assets.py`); real content replaces them in SPR-Z.7
under Rule 6.1.1 (licensed or our own, never copyrighted meme templates).
The Hebrew caption deck and topics below are a first real pass (ACT-Z.4,
spec §14.3) — usable as-is, meant to grow and be tone-reviewed, not a
placeholder in the same sense as the bank images.
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from memz.models import CaptionCard, CaptionDeck, MemeImage, Pack, PackImage, Topic

HEBREW = CaptionDeck.HEBREW

ASSETS = Path(__file__).resolve().parents[2] / "seed_assets"

# (slug, name, description, order). A public pack is a category (data_model.md).
PACKS = [
    ("family", "משפחה", "רגעים מהבית: ארוחות, טיולים, ימי ראשון.", 0),
    ("animals", "חיות", "חתולים, כלבים ושאר חברים עם פרצוף.", 1),
    ("work", "עבודה", "פגישות, מיילים, וכל מה שביניהם.", 2),
    ("school", "בית ספר", "שיעורים, מבחנים והפסקות.", 3),
]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# ACT-Z.4: a first, family-safe Hebrew caption deck (spec §5.2, Cards mode).
CAPTION_CARDS_HE = [
    "כשאמא מתקשרת בדיוק כשמדברים עליה",
    "כשמישהו אומר \"בוא נדבר רגע\"",
    "אני אחרי קפה ראשון של הבוקר",
    "כשהוואטסאפ הקבוצתי מתחיל לרעוד ב-2 בלילה",
    "כשמישהו שואל \"מה שלומך\" ומתכוון לזה",
    "הפרצוף שלי כשהאינטרנט נופל באמצע פגישה",
    "כשמוצאים חמישים שקל בכיס של מכנס ישן",
    "כשאומרים \"רק עוד חמש דקות\" בבוקר",
    "כשמישהו לוקח את החטיף האחרון בלי לשאול",
    "אני מנסה להיראות עסוק כשהבוס עובר ליד",
    "כשהילד שואל \"עוד כמה זמן\" בדקה השנייה של הנסיעה",
    "כשסוף סוף מוצאים חניה קרוב",
    "כשמישהו שר לא במקום בשיר יום הולדת",
    "הפרצוף כשמבינים שזו יום שני, לא שלישי",
    "כשמישהו אומר \"אני לא כועס\" בטון שאומר בדיוק ההפך",
    "כשהמקרר ריק אבל בודקים אותו בכל זאת",
    "כשמישהו שואל אם אפשר לוותר על הישיבה",
    "אני שומע את המילה \"בקיצור\" ויודע שזה לא יהיה בקיצור",
    "כשהתראה על הטלפון מפריעה בדיוק בזמן הכי לא נוח",
    "כשמנסים להירדם ופתאום נזכרים בכל מה שצריך לעשות מחר",
    "כשמישהו מבקש \"רק שאלה קטנה\" לפני שדוחפים שאלה ענקית",
    "כשהמורה אומרת \"בחינת פתע\"",
    "אני מנסה לזכור איפה חניתי",
    "כשמישהו אומר \"זה ממש לא קשה\" ומתחיל להסביר משהו מסובך",
    "כשמישהו פותח פה עם אוכל ומדבר בכל זאת",
    "כשמגלים שהיום שכולם ציפו לו סוף סוף הגיע",
    "כשמישהו שואל \"אתה בטוח?\" בפעם השלישית",
    "הפרצוף כשמבינים שהשכחתי את הטלפון בבית",
    "כשמישהו מבטיח \"עוד חמש דקות ואני שם\"",
    "כשהגשם מתחיל בדיוק כשיוצאים בלי מטרייה",
    "כשמישהו אומר \"בואו נעשה את זה מהר\" ולוקח שעתיים",
    "כשמישהו שם לי משימה חדשה חמש דקות לפני שיוצאים",
    "אני שומע מישהו לועס צ'יפס לידי בשקט מוחלט",
    "כשמישהו שואל למה לא עניתי, ואני הייתי ממש שם",
    "כשגומרים סדרה שלמה בלילה אחד ומתחרטים בבוקר",
    "כשמישהו אומר \"תזכיר לי\" ואני יודע שגם אני אשכח",
    "הפרצוף שלי כשמנצחים במשחק בגלל מזל בלבד",
    "כשמישהו מקליד \"תתקשר כשתתפנה\" ומתכוון עכשיו",
    "כשהילד נרדם בדיוק כשמגיעים הביתה",
    "כשמישהו אומר \"קצת פרגון לא יזיק\" באמצע ריב",
]

TOPICS_HE = [
    "יום שני בבוקר",
    "פקקים",
    "חופש גדול",
    "ערב שישי",
    "הפסקת קפה",
    "ראש השנה",
    "יום ראשון בעבודה",
    "שיעורי בית",
    "טיול משפחתי",
    "ליל הסדר",
    "יום גשום",
    "מבחנים",
    "חתונה",
    "יום הולדת",
    "חופשה בים",
]


class Command(BaseCommand):
    help = "Seed memz's public packs, bank, caption deck and topics, one time only."

    def handle(self, *args, **options):
        verbosity = int(options.get("verbosity", 1))
        created_packs = created_images = linked = skipped = 0

        for slug, name, description, order in PACKS:
            pack, made = Pack.objects.get_or_create(
                owner=None, slug=slug,
                defaults={"name": name, "description": description, "is_public": True, "order": order},
            )
            created_packs += int(made)

            folder = ASSETS / slug
            files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES) if folder.is_dir() else []
            for position, path in enumerate(files):
                key = f"{slug}/{path.name}"
                image = MemeImage.objects.filter(seed_key=key).first()
                if image is None:
                    image = MemeImage(
                        owner=None, visibility=MemeImage.PUBLIC, moderation_status=MemeImage.APPROVED,
                        moderation_note="seeded placeholder (SPR-Z.1); replaced by licensed content in SPR-Z.7",
                        seed_key=key, title=path.stem.replace("-", " ").replace("_", " "),
                    )
                    with path.open("rb") as fh:
                        image.file.save(path.name, File(fh), save=True)
                    created_images += 1
                else:
                    skipped += 1
                _link, made = PackImage.objects.get_or_create(pack=pack, image=image, defaults={"order": position})
                linked += int(made)

        deck, deck_made = CaptionDeck.objects.get_or_create(
            owner=None, name="חפיסה ראשונה", defaults={"is_public": True, "language": HEBREW},
        )
        cards_created = 0
        if not deck.cards.exists():   # coarse one-time rule: seed only an empty deck
            CaptionCard.objects.bulk_create([
                CaptionCard(deck=deck, text=text, order=i) for i, text in enumerate(CAPTION_CARDS_HE)
            ])
            cards_created = len(CAPTION_CARDS_HE)

        topics_created = 0
        if not Topic.objects.filter(owner=None, is_public=True).exists():
            Topic.objects.bulk_create([
                Topic(text=text, owner=None, is_public=True, language=HEBREW) for text in TOPICS_HE
            ])
            topics_created = len(TOPICS_HE)

        if verbosity:
            self.stdout.write(
                f"seed_memz: packs +{created_packs}, images +{created_images} "
                f"(left alone {skipped}), links +{linked}, "
                f"caption cards +{cards_created}, topics +{topics_created}"
            )
