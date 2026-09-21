"""Import SensorLab's first lab — Free Fall / Measuring g — exactly once.

**Read this before changing anything below.** `render.yaml`'s start command
runs every `seed_*` command in this repo on **every deploy**. ustrip's
version used to delete and recreate its rows each time; its Sprint 5 then
gave family members a button that wrote to the same tables, so the next
unrelated deploy would have silently erased everything they had added. It
was caught before it did, and `seed_ustrip.py` carries the note.

SensorLab is on the same path: `data_model.md` §12 anticipates
teacher-authored content, in these exact tables. So the rule here is the one
`seed_memz` settled on, and it is deliberately coarse:

    if the lab already exists, do nothing at all.

Not "create what is missing" — that would resurrect a block an author
deleted on purpose, on every deploy, forever. Once the lab exists it belongs
to the database, not to this file. To change the published lab, edit it in
the admin; to re-import from scratch, delete the lab first and let the next
run rebuild it.

---

**A content rule this file has to keep, because no serializer can.** The lab
never states the accepted value of *g* before the Analysis step. SL-B2
withholds `expected_value` from students so that "measure g" does not become
"confirm g" — and writing "gravity is 9.81 m/s²" into the Learn prose would
hand the answer over through a field that *is* meant to be sent. So the text
below says "the accepted value"; the number lives in
`AnalysisConfig.expected_value`, server-side, and reaches the student when
their result is graded. There is a test.

**The physics, since the choice of computation is not obvious.** An
accelerometer measures *proper* acceleration — what its own springs feel —
not motion. A phone lying still is being pushed up by the table hard enough
to hold it against gravity, so it reads the full strength of gravity. A
phone in free fall has nothing pushing it and reads close to zero. That
inversion is what the Predict step is aimed at: it is the answer almost
everybody gets wrong first, which is exactly what makes it worth predicting.
Measuring g is therefore the *easy* half — a stationary phone and a mean.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from sensorlab.models import (
    AnalysisConfig,
    ContentBlock,
    ExperimentConfig,
    Lab,
    PredictionChoice,
    PredictionQuestion,
    SensorRequirement,
    Track,
)

TRACK_SLUG = "free-fall"
LAB_SLUG = "measuring-g"

TRACK = {
    "slug": TRACK_SLUG,
    "title_en": "Free Fall",
    "title_he": "נפילה חופשית",
    "description_en": (
        "What a falling object actually experiences — and why the answer "
        "surprises almost everyone the first time they measure it."
    ),
    "description_he": (
        "מה באמת מרגיש גוף נופל — ולמה התשובה מפתיעה כמעט כל אחד בפעם "
        "הראשונה שהוא מודד אותה."
    ),
    "icon": "🍎",
    "order": 1,
    "is_published": True,
}

LAB = {
    "slug": LAB_SLUG,
    "title_en": "Measuring g",
    "title_he": "מדידת g",
    "summary_en": (
        "Your phone contains a scale. Use it to measure the strength of "
        "gravity where you are — then work out what it reads on the way down."
    ),
    "summary_he": (
        "בטלפון שלך יש משקל. נשתמש בו כדי למדוד את עוצמת הכבידה במקום שבו "
        "אתם נמצאים — ואז נבין מה הוא מראה בדרך למטה."
    ),
    "mode": Lab.Mode.LIVE_SENSOR,
    "estimated_minutes": 12,
    "order": 1,
    "is_published": True,
}

BLOCKS = (
    {
        "step": ContentBlock.Step.INTRO,
        "kind": ContentBlock.Kind.TEXT,
        "order": 1,
        "body_en": (
            "Somewhere inside your phone is a tiny weight on tiny springs. "
            "That is the accelerometer, and it is the only instrument this "
            "lab needs.\n\n"
            "One warning before you touch it. It does **not** measure how "
            "fast the phone is moving, and it does not measure gravity "
            "directly. It measures something slightly different — and that "
            "difference is the entire lab."
        ),
        "body_he": (
            "בתוך הטלפון שלך יש משקולת זעירה על קפיצים זעירים. זה "
            "מד־התאוצה, וזה כל המכשיר שהמעבדה הזו צריכה.\n\n"
            "אזהרה אחת לפני שמתחילים: הוא **אינו** מודד באיזו מהירות הטלפון "
            "נע, והוא אינו מודד כבידה באופן ישיר. הוא מודד משהו אחר במקצת — "
            "וההבדל הזה הוא כל המעבדה."
        ),
    },
    # ----------------------------------------------------------------
    # The Learn step, rewritten in SL-M1.
    #
    # The first version was three short paragraphs that asserted "an
    # accelerometer measures proper acceleration" and stopped. Avi read it on
    # his phone and said, correctly, that it explains nothing: the question a
    # student is owed is *why gravity is measured as an acceleration at all*.
    #
    # So it derives the thing instead. Proof mass, Newton's second law, the
    # two cases that fall out of it, and the reason the sensor cannot tell
    # gravity from acceleration — which is the equivalence principle, a fact
    # about nature rather than a limitation of a cheap chip.
    #
    # The equations are identical in both languages, and a test enforces
    # that: prose is translated, mathematics is not, and a formula that
    # differs between languages is a transcription error.
    # ----------------------------------------------------------------
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.TEXT,
        "order": 1,
        "body_en": (
            "### What is actually inside\n\n"
            "An accelerometer is not a gravity meter. Inside the chip is a "
            "tiny block — the **proof mass** — held between springs, and the "
            "only thing the device can measure is how far that block has "
            "shifted from its resting position.\n\n"
            "That shift tells it one thing: the force the *springs* are "
            "exerting. Nothing else. Keep hold of that, because everything "
            "surprising below follows from it."
        ),
        "body_he": (
            "### מה באמת נמצא בפנים\n\n"
            "מד־תאוצה אינו מד־כבידה. בתוך השבב יש גוש זעיר — **מסת המבחן** — "
            "המוחזק בין קפיצים, והדבר היחיד שהמכשיר יודע למדוד הוא כמה הגוש "
            "הזה הוסט ממקום המנוחה שלו.\n\n"
            "ההסטה הזו מספרת לו דבר אחד: את הכוח שה*קפיצים* מפעילים. שום דבר "
            "אחר. כדאי לזכור את זה, כי כל מה שמפתיע בהמשך נובע מכאן."
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.TEXT,
        "order": 2,
        "body_en": (
            "### Newton, applied to that little block\n\n"
            "Two forces act on the proof mass: gravity, and the springs. "
            "Newton's second law says their sum is its mass times its "
            "acceleration:\n\n"
            "$$m\\vec{g} + \\vec{F}_{\\text{spring}} = m\\vec{a}$$\n\n"
            "Here $\\vec{a}$ is the acceleration of the phone itself — how it "
            "is moving through the room. Divide through by $m$ and rearrange "
            "to get what the springs feel, per unit mass. That quantity has a "
            "name: **proper acceleration**, and it is what the chip reports."
        ),
        "body_he": (
            "### ניוטון, בהחלה על הגוש הקטן הזה\n\n"
            "שני כוחות פועלים על מסת המבחן: הכבידה, והקפיצים. החוק השני של "
            "ניוטון אומר שסכומם שווה למסה כפול התאוצה שלה:\n\n"
            "$$m\\vec{g} + \\vec{F}_{\\text{spring}} = m\\vec{a}$$\n\n"
            "כאן $\\vec{a}$ היא התאוצה של הטלפון עצמו — איך הוא נע בחדר. "
            "נחלק ב־$m$ ונבודד את מה שהקפיצים מרגישים, ליחידת מסה. לגודל הזה "
            "יש שם: **תאוצה עצמית**, וזה מה שהשבב מדווח."
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.FORMULA,
        "order": 3,
        # Identical in both languages, which is why the bilingual test skips
        # formula blocks rather than demanding a difference.
        #
        # Now LaTeX. It used to be "|a| = √(a_x² + a_y² + a_z²)" typed by
        # hand — and before that it mixed a Unicode subscript for x with
        # plain underscores for y and z, because Unicode HAS no subscript y
        # or z. Both were caught by looking at the rendered step.
        "body_en": (
            "$$\\vec{a}_{\\text{proper}} \\;=\\; "
            "\\frac{\\vec{F}_{\\text{spring}}}{m} \\;=\\; \\vec{a} - \\vec{g}$$"
        ),
        "body_he": (
            "$$\\vec{a}_{\\text{proper}} \\;=\\; "
            "\\frac{\\vec{F}_{\\text{spring}}}{m} \\;=\\; \\vec{a} - \\vec{g}$$"
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.TEXT,
        "order": 4,
        "body_en": (
            "### Two cases, and they are the whole lab\n\n"
            "**On the table.** The phone goes nowhere, so $\\vec{a} = 0$:\n\n"
            "$$\\vec{a}_{\\text{proper}} = 0 - \\vec{g} = -\\vec{g}$$\n\n"
            "The springs are compressed by the table holding the phone up, "
            "and the reading has the full size of $\\vec{g}$, pointing "
            "**upward** — away from the Earth, opposite to gravity itself. A "
            "phone sitting still is already measuring what you came here to "
            "measure.\n\n"
            "**In free fall.** Nothing touches the phone, so gravity alone "
            "acts and $\\vec{a} = \\vec{g}$:\n\n"
            "$$\\vec{a}_{\\text{proper}} = \\vec{g} - \\vec{g} = 0$$\n\n"
            "The case and the proof mass fall together at exactly the same "
            "rate, so the springs are neither stretched nor squashed. The "
            "accelerometer reads **zero** — while accelerating faster than at "
            "any other moment in the lab."
        ),
        "body_he": (
            "### שני מקרים, והם כל המעבדה\n\n"
            "**על השולחן.** הטלפון אינו זז לשום מקום, ולכן $\\vec{a} = 0$:\n\n"
            "$$\\vec{a}_{\\text{proper}} = 0 - \\vec{g} = -\\vec{g}$$\n\n"
            "הקפיצים נדחסים בגלל השולחן שמחזיק את הטלפון, והקריאה היא בגודל "
            "המלא של $\\vec{g}$, בכיוון **מעלה** — הרחק מכדור הארץ, הפוך "
            "לכבידה עצמה. טלפון שמונח בשקט כבר מודד בדיוק את מה שבאתם למדוד.\n\n"
            "**בנפילה חופשית.** שום דבר לא נוגע בטלפון, ולכן פועלת רק הכבידה "
            "ו־$\\vec{a} = \\vec{g}$:\n\n"
            "$$\\vec{a}_{\\text{proper}} = \\vec{g} - \\vec{g} = 0$$\n\n"
            "המארז ומסת המבחן נופלים יחד בדיוק באותו קצב, ולכן הקפיצים אינם "
            "נמתחים ואינם נדחסים. מד־התאוצה מראה **אפס** — בדיוק כשהוא מאיץ "
            "מהר יותר מבכל רגע אחר במעבדה."
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.CALLOUT,
        "order": 5,
        "body_en": (
            "**Why can it not just measure gravity directly?**\n\n"
            "Because nothing can. Einstein's **equivalence principle** says "
            "no experiment performed inside a sealed box can tell the "
            "difference between sitting still in a gravitational field and "
            "accelerating through empty space. The two are not merely hard to "
            "separate — they are physically the same situation.\n\n"
            "So the $-\\vec{g}$ in the equation above is not a flaw in a "
            "cheap chip. It is the reason gravity has to be measured "
            "*indirectly*: by measuring the force that holds you up against "
            "it. The table is doing the measuring. Your phone is just reading "
            "the table."
        ),
        "body_he": (
            "**למה אי אפשר פשוט למדוד כבידה ישירות?**\n\n"
            "כי אף אחד לא יכול. **עקרון השקילות** של איינשטיין אומר ששום ניסוי "
            "שנעשה בתוך קופסה אטומה אינו יכול להבחין בין לשבת במנוחה בשדה "
            "כבידה לבין להאיץ בחלל ריק. השניים אינם רק קשים להפרדה — מבחינה "
            "פיזיקלית הם אותו מצב.\n\n"
            "לכן ה־$-\\vec{g}$ במשוואה שלמעלה אינו פגם בשבב זול. זו הסיבה "
            "שכבידה נמדדת *בעקיפין*: על ידי מדידת הכוח שמחזיק אתכם נגדה. "
            "השולחן הוא זה שמודד. הטלפון רק קורא את השולחן."
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.TEXT,
        "order": 6,
        "body_en": (
            "### One number, whichever way up\n\n"
            "The chip reports three axes, and your phone has no idea how you "
            "are holding it. Take the magnitude and orientation stops "
            "mattering:\n\n"
            "$$|\\vec{a}| = \\sqrt{a_x^2 + a_y^2 + a_z^2}$$\n\n"
            "That single number, averaged over a few still seconds, is your "
            "measurement. Afterwards you will compare it with the accepted "
            "value using\n\n"
            "$$\\varepsilon = \\frac{\\left|a_{\\text{measured}} - "
            "a_{\\text{accepted}}\\right|}{a_{\\text{accepted}}} \\times 100\\%$$\n\n"
            "Under 5% from a phone on a kitchen table is a genuinely good "
            "result — for a sensor that costs a few cents."
        ),
        "body_he": (
            "### מספר אחד, בכל כיוון שתחזיקו\n\n"
            "השבב מדווח על שלושה צירים, ולטלפון אין מושג איך אתם מחזיקים "
            "אותו. לוקחים את הגודל, והכיוון מפסיק להיות משנה:\n\n"
            "$$|\\vec{a}| = \\sqrt{a_x^2 + a_y^2 + a_z^2}$$\n\n"
            "המספר היחיד הזה, ממוצע על פני כמה שניות של שקט, הוא המדידה שלכם. "
            "בהמשך תשוו אותו לערך המקובל באמצעות\n\n"
            "$$\\varepsilon = \\frac{\\left|a_{\\text{measured}} - "
            "a_{\\text{accepted}}\\right|}{a_{\\text{accepted}}} \\times 100\\%$$\n\n"
            "פחות מ‑5% מטלפון על שולחן במטבח היא תוצאה טובה באמת — בשביל חיישן "
            "שעולה כמה אגורות."
        ),
    },
    {
        "step": ContentBlock.Step.ANALYSIS,
        "kind": ContentBlock.Kind.TEXT,
        "order": 1,
        "body_en": (
            "Compare your figure with the accepted value on your results "
            "screen, then ask the only question that matters: was the "
            "difference your phone, or was it you?"
        ),
        "body_he": (
            "השוו את המספר שלכם לערך המקובל שמופיע במסך התוצאות, ואז שאלו "
            "את השאלה היחידה שחשובה: ההפרש נבע מהטלפון, או מכם?"
        ),
    },
)

QUESTIONS = (
    {
        "kind": PredictionQuestion.Kind.MULTIPLE_CHOICE,
        "order": 1,
        "prompt_en": (
            "Your phone is falling freely through the air with nothing "
            "touching it. What does its accelerometer read?"
        ),
        "prompt_he": (
            "הטלפון שלך נופל בחופשיות באוויר, בלי שדבר נוגע בו. מה מד־התאוצה "
            "שלו מראה?"
        ),
        "choices": (
            ("About the same as on the table", "בערך אותו דבר כמו על השולחן", False),
            ("Close to zero", "קרוב לאפס", True),
            ("Twice what it reads on the table", "כפול ממה שהוא מראה על השולחן", False),
            ("It depends how fast it is going", "תלוי באיזו מהירות הוא נע", False),
        ),
    },
    {
        "kind": PredictionQuestion.Kind.NUMERIC,
        "order": 2,
        "prompt_en": (
            "Lying flat and completely still on a table, what magnitude will "
            "your phone report, in m/s²?"
        ),
        "prompt_he": (
            "כשהטלפון מונח שטוח ובשקט מוחלט על השולחן, איזה גודל הוא ידווח, "
            "במ׳/ש²?"
        ),
        "correct_value": 9.81,
        "tolerance": 10.0,
        "choices": (),
    },
    {
        "kind": PredictionQuestion.Kind.GRAPH_SKETCH,
        "order": 3,
        "prompt_en": (
            "Sketch |a| against time for a phone that sits still, is lifted, "
            "dropped onto a cushion, and comes to rest."
        ),
        "prompt_he": (
            "שרטטו |a| כפונקציה של הזמן עבור טלפון שמונח בשקט, מורם, מופל על "
            "כרית, ונח."
        ),
        "choices": (),
    },
)

EXPERIMENT = {
    "instructions_en": (
        "Lay the phone flat on a table, screen up, and let go of it. Tap "
        "Record and leave it completely still for three seconds.\n\n"
        "That is the whole measurement. The hard part is not moving."
    ),
    "instructions_he": (
        "הניחו את הטלפון שטוח על השולחן, המסך למעלה, ועזבו אותו. הקישו על "
        "הקלטה והשאירו אותו בשקט מוחלט לשלוש שניות.\n\n"
        "זו כל המדידה. החלק הקשה הוא לא להזיז."
    ),
    # A request, not a setting — spec §4.1. The phone in the spike answered
    # ~63 Hz to a request for 200, and 60 is plenty for a stationary mean.
    "requested_hz": 60,
    "max_duration_ms": 3000,
    "trigger_kind": ExperimentConfig.Trigger.MANUAL,
}

#: No `axis_filter`: the magnitude of all three axes is the point, because a
#: phone does not know how it is being held.
SENSORS = (("accelerometer", True, ""),)

ANALYSIS = {
    "computation": AnalysisConfig.Computation.MEAN,
    "expected_source": AnalysisConfig.ExpectedSource.CONSTANT,
    "expected_value": 9.81,
    "unit": "m/s²",
    "pass_tolerance": 5.0,
    "explanation_en": (
        "The mean of |a| while your phone was still is the strength of "
        "gravity where you are — read off the table's push, which balances "
        "it exactly.\n\n"
        "Came out low? The phone probably moved. High? Something was "
        "vibrating: a fan, a fridge, a road outside.\n\n"
        "And the falling phone. Nothing was pushing it, so its springs felt "
        "nothing at all. That is what weightlessness is — not the absence of "
        "gravity, but the absence of anything resisting it."
    ),
    "explanation_he": (
        "הממוצע של |a| בזמן שהטלפון היה בשקט הוא עוצמת הכבידה במקום שבו "
        "אתם נמצאים — נקראת מתוך הדחיפה של השולחן, שמאזנת אותה בדיוק.\n\n"
        "יצא נמוך? כנראה שהטלפון זז. גבוה? משהו רעד: מאוורר, מקרר, כביש "
        "בחוץ.\n\n"
        "ומה עם הטלפון הנופל? שום דבר לא דחף אותו, ולכן הקפיצים שלו לא "
        "הרגישו כלום. זו חוסר משקל — לא היעדר כבידה, אלא היעדר כל דבר "
        "שמתנגד לה."
    ),
}


class Command(BaseCommand):
    help = "Import the Free Fall track and the Measuring g lab, once."

    def handle(self, *args, **options):
        existing = Lab.objects.filter(slug=LAB_SLUG).first()
        if existing is not None:
            # Say which of the two things happened. A seed command that
            # prints nothing looks identical whether it imported a course or
            # skipped one, and it runs inside a deploy log where that output
            # is the only evidence anyone will ever have.
            self.stdout.write(
                f"seed_sensorlab: lab '{LAB_SLUG}' already exists (pk={existing.pk}) — "
                f"left untouched, nothing written. Edit it in the admin, or delete "
                f"it to re-import."
            )
            return

        with transaction.atomic():
            track, track_is_new = Track.objects.get_or_create(
                slug=TRACK_SLUG, defaults={k: v for k, v in TRACK.items() if k != "slug"}
            )
            lab = Lab.objects.create(track=track, **LAB)

            for block in BLOCKS:
                ContentBlock.objects.create(lab=lab, **block)

            for question in QUESTIONS:
                choices = question["choices"]
                row = PredictionQuestion.objects.create(
                    lab=lab, **{k: v for k, v in question.items() if k != "choices"}
                )
                for order, (text_en, text_he, correct) in enumerate(choices, start=1):
                    PredictionChoice.objects.create(
                        question=row, text_en=text_en, text_he=text_he,
                        is_correct=correct, order=order,
                    )

            config = ExperimentConfig.objects.create(lab=lab, **EXPERIMENT)
            for sensor, required, axis in SENSORS:
                SensorRequirement.objects.create(
                    config=config, sensor=sensor, is_required=required, axis_filter=axis
                )

            AnalysisConfig.objects.create(lab=lab, **ANALYSIS)

        self.stdout.write(self.style.SUCCESS(
            f"seed_sensorlab: created lab '{LAB_SLUG}' in track '{TRACK_SLUG}' "
            f"({'new track' if track_is_new else 'existing track'}) — "
            f"{lab.content_blocks.count()} content blocks, "
            f"{lab.prediction_questions.count()} prediction questions, "
            f"{config.sensor_requirements.count()} sensor requirement(s)."
        ))
