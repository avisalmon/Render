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
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.TEXT,
        "order": 1,
        "body_en": (
            "The accelerometer reports **proper acceleration**: what its own "
            "springs feel.\n\n"
            "Lying still on a table, your phone is not accelerating anywhere "
            "— and yet the table is pushing up on it hard enough to hold it "
            "against gravity. The springs feel that push. So a phone at rest "
            "reads the full strength of gravity, pointing up.\n\n"
            "Now take the table away."
        ),
        "body_he": (
            "מד־התאוצה מדווח על **תאוצה עצמית**: מה שהקפיצים שלו מרגישים.\n\n"
            "כשהטלפון מונח בשקט על השולחן הוא אינו מאיץ לשום מקום — ובכל "
            "זאת השולחן דוחף אותו כלפי מעלה בכוח שמחזיק אותו נגד הכבידה. "
            "הקפיצים מרגישים את הדחיפה. לכן טלפון במנוחה מראה את עוצמת "
            "הכבידה במלואה, בכיוון מעלה.\n\n"
            "ועכשיו נסלק את השולחן."
        ),
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.FORMULA,
        "order": 2,
        # The same sentence in both languages, which is why the bilingual
        # test skips formula blocks rather than demanding a difference.
        #
        # `a_x`, not `aₓ`. The first version mixed a Unicode subscript for x
        # with plain underscores for y and z, because Unicode HAS no subscript
        # y or z — so it rendered as "aₓ² + a_y² + a_z²", inconsistent and
        # visibly wrong to anyone reading the physics. Caught in SL-D2 by
        # looking at the rendered step, not by a test. Formula blocks are
        # literal by design (Markdown would read `_` as emphasis), so what is
        # written here is exactly what a student sees.
        "body_en": "|a| = √(a_x² + a_y² + a_z²)",
        "body_he": "|a| = √(a_x² + a_y² + a_z²)",
    },
    {
        "step": ContentBlock.Step.LEARN,
        "kind": ContentBlock.Kind.CALLOUT,
        "order": 3,
        "body_en": (
            "Your phone does not know which way up it is being held, so no "
            "single axis holds the answer. Take the magnitude of all three "
            "and orientation stops mattering.\n\n"
            "How close is close enough? Percent error is "
            "`|measured − accepted| / accepted × 100`. Under 5% from a phone "
            "on a kitchen table is a genuinely good result."
        ),
        "body_he": (
            "הטלפון שלך אינו יודע באיזה כיוון מחזיקים אותו, ולכן אף ציר בודד "
            "אינו מחזיק את התשובה. לוקחים את הגודל של שלושת הצירים יחד, "
            "והכיוון מפסיק להיות משנה.\n\n"
            "מה נחשב קרוב מספיק? שגיאה באחוזים היא "
            "`|נמדד − מקובל| / מקובל × 100`. פחות מ‑5% מטלפון על שולחן "
            "במטבח היא תוצאה טובה באמת."
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
