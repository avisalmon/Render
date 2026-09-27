"""The MTP guidance said the opposite of what it now means.

Avi's correction: an MTP is a slogan of a few words, short enough to print on
a t-shirt, with at most one fifteen-word line of expansion beside it. The
seeded copy for the MTP slot said the reverse in as many words ("not a slogan
and not a vision statement"), and the handout is the thing people read during
the lecture, so it cannot be left contradicting the app they are about to use.

`seed_exo` deliberately never overwrites, which is what protects Avi's own
edits on every deploy. That rule is right and is not being weakened here: this
migration only rewrites a row that still carries the specific sentence being
retracted. Anything edited since keeps whatever it says now, and a row already
carrying the new text is left alone.

The values are written out in full rather than imported from `exo/seed/`,
because a migration has to mean the same thing in a year as it does today and
the seed modules will keep changing.
"""

from django.db import migrations

#: The retraction is matched on these, not on the whole body: a row still
#: carrying the sentence is either untouched or edited in a way that kept the
#: wrong claim, and in both cases the sentence has to go.
CONTRADICTS_HE = "לא סיסמה ולא הצהרת חזון"
CONTRADICTS_EN = "not a slogan and not a vision statement"

NEW_SHORT_DEF_HE = (
    "השינוי שבגללו אתה קיים, בכמה מילים. סלוגן שאפשר להדפיס על חולצה, "
    "לא הצהרת חזון. לא מה שאתה מוכר."
)
NEW_SHORT_DEF_EN = (
    "The change you exist to make, said in a handful of words. A slogan you "
    "could print on a t-shirt, not a vision statement. Not what you sell."
)
NEW_HINT_HE = (
    "אם זה יצליח לגמרי — מה ישתנה בעולם? עכשיו קצר את זה לשלוש־ארבע מילים, "
    "בלי להזכיר את המוצר. אם אי אפשר לחזור על זה מהזיכרון, זה עדיין ארוך מדי."
)
NEW_HINT_EN = (
    "If this worked completely, what would be different in the world? Now cut "
    "it to three or four words, with no product in them. If people cannot "
    "repeat it from memory, it is still too long."
)

OLD_SHORT_DEF_HE = (
    "ה'למה' הגדול והשאפתני שכל השאר תלוי בו. לא מה אתה מוכר — אלא השינוי "
    "שבגללו אתה קיים."
)
OLD_SHORT_DEF_EN = (
    "The huge, aspirational 'why' that everything else hangs from. Not what "
    "you sell — the change you exist to make."
)

NEW_BODY_HE = """המטרה היא סלוגן. כמה מילים, קצר מספיק להדפסה על חולצה
ולחזרה מהזיכרון, שאומרות איזה שינוי אתה קיים בשבילו. לא מה אתה מוכר, ולא
הצהרת חזון באורך פסקה.

כאן נמצא המנוף האמיתי: מטרה גדולה מושכת אנשים שלא עובדים אצלך. מתנדבים,
שותפים, מפתחים ולקוחות מוקדמים מצטרפים כי הם רוצים שהדבר הזה יקרה, לא כי
שילמת להם. ארגון עם מטרה קטנה חייב לקנות כל יחידת תשומת לב שהוא מקבל.

דוגמה: המטרה של TED היא "רעיונות ששווה להפיץ". היא אפשרה לאלפי אנשים ברחבי
העולם להפעיל אירועי TEDx בעצמם, בלי שאיש מהם הועסק על ידי TED.

מה בדרך כלל משתבש: כותבים פסקה. אם צריך לקרוא את המטרה שלך מהדף, היא כבר
לא עושה את העבודה שלה, כי אף אחד לא מגייס אנשים למשהו שהוא לא זוכר. הכישלון
השני הוא לנסח משהו שנשמע יפה ואי אפשר להתנגד לו: אם אף אחד לא יכול לחלוק על
המטרה שלך, היא כנראה לא אומרת כלום.

ואם צריך עוד הסבר, הוא נכנס למשפט אחד קצר לצד הסלוגן. לא לתוכו."""

NEW_BODY_EN = """The purpose is a slogan. A handful of words, short
enough to print on a t-shirt and repeat from memory, naming the change you
exist to make. Not what you sell, and not a paragraph-long vision statement.

This is where the real leverage sits: a large purpose attracts people who do
not work for you. Volunteers, partners, developers and early customers show up
because they want the thing to happen, not because you paid them. An
organisation with a small purpose has to buy every unit of attention it gets.

Example: TED's purpose is "ideas worth spreading". It let thousands of people
around the world run TEDx events themselves, none of them employed by TED.

What usually goes wrong: people write a paragraph. If your purpose has to be
read off the page it has already stopped doing its job, because nobody is
recruited by something they cannot remember. The second failure is writing
something that sounds good and that nobody could possibly disagree with: if
your purpose cannot be argued with, it probably is not saying anything.

If it needs more explanation, that goes in one short line beside the slogan.
Not inside it."""


def retract(apps, schema_editor):
    ExoAttribute = apps.get_model("exo", "ExoAttribute")
    LearnResource = apps.get_model("exo", "LearnResource")

    attribute = ExoAttribute.objects.filter(key="mtp").first()
    if attribute is not None:
        changed = []
        if attribute.short_def_he.strip() == OLD_SHORT_DEF_HE:
            attribute.short_def_he = NEW_SHORT_DEF_HE
            changed.append("short_def_he")
        if attribute.short_def_en.strip() == OLD_SHORT_DEF_EN:
            attribute.short_def_en = NEW_SHORT_DEF_EN
            changed.append("short_def_en")
        # The hint is rewritten alongside the definition it belongs to: a slot
        # that now asks for three words must not still prompt for one line.
        if "short_def_he" in changed:
            attribute.prompt_hint_he = NEW_HINT_HE
            changed.append("prompt_hint_he")
        if "short_def_en" in changed:
            attribute.prompt_hint_en = NEW_HINT_EN
            changed.append("prompt_hint_en")
        if changed:
            attribute.save(update_fields=changed)

    page = LearnResource.objects.filter(key="attr-mtp").first()
    if page is not None:
        changed = []
        if CONTRADICTS_HE in page.body_he:
            page.body_he = NEW_BODY_HE
            changed.append("body_he")
        if CONTRADICTS_EN in page.body_en:
            page.body_en = NEW_BODY_EN
            changed.append("body_en")
        if changed:
            page.save(update_fields=changed)


def unretract(apps, schema_editor):
    """Deliberately does nothing.

    Reversing would put the contradicting sentence back, and there is no
    version of this app in which that text is correct. The migration is
    reversible so the chain can be unwound; the content stays fixed.
    """


class Migration(migrations.Migration):

    dependencies = [("exo", "0005_mtp_is_a_slogan")]

    operations = [migrations.RunPython(retract, unretract)]
