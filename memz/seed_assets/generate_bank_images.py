"""SPR-Z.7 / ACT-Z.1: generate a real illustrated batch for the public
bank, replacing the flat-shape placeholders from make_assets.py (spec
Rule 6.1.1 — licensed or our own; these are OpenAI-generated for memz,
not photos of real people or copyrighted meme templates).

Run (costs real API money — gpt-image-1, medium quality, ~$0.04/image):

    .\\env\\Scripts\\python.exe memz\\seed_assets\\generate_bank_images.py

Restart-safe: a file that already exists on disk is never regenerated,
so an interrupted run picks up exactly where it left off and a second
run of the same list is free. Output goes to
`memz/seed_assets/<pack-slug>/<pack-slug>-NN.png`, the same layout
`seed_memz` already reads (keyed by relative path as `seed_key`), so
wiring these in is `seed_memz` running again — the extra packs need
adding to its own `PACKS` list first (SPR-Z.7 does that).
"""

import os
import sys
import time
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.conf import settings  # noqa: E402
from openai import OpenAI  # noqa: E402

HERE = Path(__file__).resolve().parent

STYLE_SUFFIX = (
    " Flat, minimal vector illustration, like a modern app onboarding graphic. "
    "Simple geometric shapes, soft rounded forms, no photorealism, no 3D render. "
    "Absolutely no text, no words, no letters, no numbers, no logos, no watermarks "
    "anywhere in the image. No real or recognizable people, no celebrities, no "
    "brand names. Generous empty space at the top of the frame for a caption to "
    "be added later. Square 1:1 composition. Warm, friendly, family-safe."
)

# (slug, name, description, order, palette words) — palette is a style hint
# only (the model isn't given hex codes), enough to keep one pack visually
# distinct from the next without every image looking identical.
PACKS = [
    ("family", "משפחה", "רגעים מהבית: ארוחות, טיולים, ימי ראשון.", 0, "warm beige and coral"),
    ("animals", "חיות", "חתולים, כלבים ושאר חברים עם פרצוף.", 1, "soft sage green and mustard yellow"),
    ("work", "עבודה", "פגישות, מיילים, וכל מה שביניהם.", 2, "cool slate blue and grey"),
    ("school", "בית ספר", "שיעורים, מבחנים והפסקות.", 3, "bright sky blue and sunshine yellow"),
    ("friends", "חברים", "מפגשים, בדיחות פנימיות ותמונות קבוצתיות.", 4, "playful pink and lavender"),
    ("food", "אוכל", "ארוחות, חטיפים וקינוחים שאי אפשר לעמוד בפניהם.", 5, "appetizing terracotta and cream"),
    ("holidays", "חגים", "נרות, מתנות וערבי חג משפחתיים.", 6, "deep navy and warm gold"),
    ("sports", "ספורט", "אימונים, משחקים ורגעי ניצחון.", 7, "energetic teal and orange"),
]

SCENES = {
    "family": [
        "A cheerful family sitting around a dinner table sharing a meal.",
        "Parents watching their child's school play from the audience, beaming.",
        "A family road trip, crammed in a car with luggage piled on the roof.",
        "Grandparents visiting, a big warm hug at the front door.",
        "A family gathered around a board game spread out on the living room floor.",
        "A dad surrounded by flat-pack furniture parts, instructions upside down.",
        "A mom juggling grocery bags and a phone call at the front door.",
        "Siblings on the couch dramatically fighting over the TV remote.",
        "A family photo attempt where everyone is looking a different direction.",
        "A parent reading a bedtime story to two kids tucked into bed.",
        "The whole family cleaning the house together, one kid mopping dramatically.",
        "A family staring at a broken washing machine with overflowing suds.",
    ],
    "animals": [
        "A cat sitting on top of a bookshelf, staring down judgmentally.",
        "A dog sitting guiltily next to a torn-up pillow, feathers everywhere.",
        "A cat mid-swipe, knocking a cup off a table.",
        "A dog waiting eagerly by the front door with a leash in its mouth.",
        "Two cats squeezed together, fighting over one sunny window spot.",
        "A dog sleeping upside down in an impossibly twisted position.",
        "A cat squeezed into a cardboard box far too small for it.",
        "A colorful parrot on a perch with a mischievous, knowing look.",
        "A dog wearing a cone of shame, looking utterly dramatic about it.",
        "A hamster with its cheeks stuffed comically full of food.",
        "A cat ignoring a brand new toy, curled up happily in the box it came in.",
        "A dog and a cat sharing one small pet bed, squished together.",
    ],
    "work": [
        "Someone staring blankly at a laptop covered in dozens of browser tabs.",
        "An exhausted person slumped in a long, boring video call.",
        "Someone hiding behind a giant coffee mug in an early morning meeting.",
        "A desk completely covered in colorful sticky notes.",
        "Someone silently screaming into a pillow at their office desk.",
        "A person sprinting down a hallway, late for a meeting, papers flying.",
        "An inbox overflowing with unread messages, person overwhelmed at a screen.",
        "Someone quietly celebrating at their desk after finishing a big task.",
        "Two coworkers awkwardly waiting in silence for a slow elevator.",
        "Someone eating lunch at their desk one-handed while still typing.",
        "A person staring helplessly at a printer that just jammed.",
        "Someone drifting off to sleep in a long, dim afternoon meeting.",
    ],
    "school": [
        "A student staring wide-eyed at a completely blank exam paper.",
        "A kid fast asleep face-down on an open textbook.",
        "Two students passing a folded note across the classroom aisle.",
        "A teacher writing on a chalkboard, chalk dust flying everywhere.",
        "A kid sprinting joyfully out of the school doors at the final bell.",
        "A group of students cramming together around a table the night before a test.",
        "A student raising a hand confidently, clearly about to say the wrong answer.",
        "A backpack stuffed so full of books it can barely close.",
        "Kids racing each other to the front of the school lunch line.",
        "A student staring at a returned test paper with a disappointed face.",
        "A group doing classroom teamwork where only one kid is actually working.",
        "Students throwing their papers into the air on the last day of school.",
    ],
    "friends": [
        "A group of friends laughing loudly together around a small table.",
        "Friends piled onto one small couch, watching a movie together.",
        "One friend showing a phone screen while everyone else crowds in close.",
        "A group of friends taking a chaotic, squished-together group selfie.",
        "Two friends having an exaggerated, dramatic argument over something tiny.",
        "A group of friends waiting in a long line, clearly bored.",
        "Friends huddled over a giant, messy map planning a trip.",
        "One friend telling a story with huge exaggerated hand gestures to the group.",
        "A group of friends raising glasses together in a cheerful toast.",
        "A friend group squeezed uncomfortably into one small car.",
        "Two friends mid-enthusiastic high five.",
        "A group of friends sitting around a small campfire at night.",
    ],
    "food": [
        "Someone staring lovingly at a giant slice of layered cake.",
        "A person desperately searching a nearly empty fridge.",
        "A table completely overflowing with far too many dishes for one meal.",
        "Someone spilling a full cup of coffee everywhere in a rush.",
        "A proud chef presenting a slightly burnt dish with confidence anyway.",
        "Someone sneaking a midnight snack, lit only by the open fridge light.",
        "A person torn between a takeout menu and a pot on the stove.",
        "A table set for a holiday feast, warm steam rising off the food.",
        "Someone struggling to close an absurdly overstuffed sandwich.",
        "A person savoring the first sip of morning coffee, eyes closed happily.",
        "Kids making a huge flour-covered mess baking cookies together.",
        "A picnic blanket spread with far too much food for just two people.",
    ],
    "holidays": [
        "A family lighting candles together around a festively set table.",
        "Someone wrapping far too many gifts, ribbon and paper everywhere.",
        "Relatives crowded happily around one big holiday dinner table.",
        "Kids bouncing with impatience, waiting to unwrap their presents.",
        "A living room glowing with festive string lights and decorations.",
        "Someone fast asleep on the couch after an enormous holiday meal.",
        "A family playing a traditional game together at a holiday gathering.",
        "A table laid out with an abundance of festive holiday dishes.",
        "Someone struggling to fit one huge gift into an already-full car trunk.",
        "Relatives squeezing in for an oversized, slightly chaotic holiday photo.",
        "Kids in festive costumes celebrating together, delighted.",
        "A quiet, cozy holiday evening, candles glowing softly on the table.",
    ],
    "sports": [
        "Someone triumphantly crossing a finish line, arms thrown up in the air.",
        "A crowd cheering wildly from the stands at a game.",
        "Someone collapsing happily exhausted onto the grass after a workout.",
        "A coach animatedly shouting instructions from the sidelines.",
        "A team gathered in a tight huddle before a big game.",
        "Someone missing an easy shot, hands on head in disbelief.",
        "A group of friends playing a casual pickup basketball game in the park.",
        "Someone lacing up running shoes at sunrise, ready to go.",
        "A team celebrating together, piling in after a big win.",
        "A person stretching dramatically before starting a workout.",
        "A young athlete proudly holding up a small trophy.",
        "A group doing an awkward, out-of-sync workout class together.",
    ],
}


def main():
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    made = skipped = 0
    for slug, _name, _desc, _order, palette in PACKS:
        out_dir = HERE / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        scenes = SCENES[slug]
        for i, scene in enumerate(scenes, start=1):
            # JPEG, not PNG: gpt-image-1's PNG runs ~1.3MB each (96 of them is
            # ~125MB of git history for a background image nothing ever
            # displays past RENDER_WIDTH=1080 anyway); re-encoding drops that
            # to single-digit MB total with no visible quality loss.
            out_path = out_dir / f"{slug}-{i:02d}.jpg"
            if out_path.exists():
                skipped += 1
                continue
            prompt = f"{scene} Color palette: {palette}.{STYLE_SUFFIX}"
            t0 = time.time()
            try:
                r = client.images.generate(
                    model="gpt-image-1", prompt=prompt, size="1024x1024", quality="medium", n=1,
                )
                import base64
                import io

                from PIL import Image

                img_bytes = base64.b64decode(r.data[0].b64_json)
                im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                im.save(out_path, format="JPEG", quality=85, optimize=True)
                made += 1
                print(f"[{made} made, {skipped} skipped] {out_path.name} "
                      f"({out_path.stat().st_size // 1024} KB, {time.time()-t0:.0f}s)", flush=True)
            except Exception as exc:   # noqa: BLE001 - a bad prompt must not kill the whole batch
                print(f"FAILED {out_path.name}: {exc}", flush=True)
    print(f"done: {made} generated, {skipped} already existed")


if __name__ == "__main__":
    main()
