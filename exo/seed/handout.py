# -*- coding: utf-8 -*-
"""The handout text for each attribute (spec §3.2).

One entry per attribute: what it is in plain words, where the leverage
actually comes from, a real company that did it, and the part that usually
goes wrong. Written for someone reading on a phone during a lecture, which is
why each is four short paragraphs and not an essay.

Seeded into `LearnResource.body_*` as a *starting point*. The seed never
overwrites, so once Avi edits a page in the admin his version is the one that
survives every future deploy.

Hebrew is the primary text here, since that is the room this is written for;
the English is a translation of the same idea rather than a different lesson.
"""

#: key -> {"body_he": ..., "body_en": ...}
ATTRIBUTE_BODIES = {

    "mtp": {
        "body_he": """המטרה היא לא סיסמה ולא הצהרת חזון. זהו משפט אחד שמסביר
למה הארגון קיים, והוא גדול מספיק כדי שאי אפשר יהיה להשלים אותו לבד ובטווח
הקרוב.

כאן נמצא המנוף האמיתי: מטרה גדולה מושכת אנשים שלא עובדים אצלך. מתנדבים,
שותפים, מפתחים ולקוחות מוקדמים מצטרפים כי הם רוצים שהדבר הזה יקרה, לא כי
שילמת להם. ארגון עם מטרה קטנה חייב לקנות כל יחידת תשומת לב שהוא מקבל.

דוגמה: המטרה של TED היא "רעיונות ששווה להפיץ". היא אפשרה לאלפי אנשים ברחבי
העולם להפעיל אירועי TEDx בעצמם, בלי שאיש מהם הועסק על ידי TED.

מה בדרך כלל משתבש: מנסחים משהו שנשמע יפה אבל אף אחד לא יכול להתנגד לו.
אם אף אחד לא יכול לחלוק על המטרה שלך, היא כנראה לא אומרת כלום.""",
        "body_en": """The purpose is not a slogan and not a vision statement.
It is one sentence explaining why the organisation exists, large enough that
you could not possibly finish the job alone or this year.

This is where the real leverage sits: a large purpose attracts people who do
not work for you. Volunteers, partners, developers and early customers show up
because they want the thing to happen, not because you paid them. An
organisation with a small purpose has to buy every unit of attention it gets.

Example: TED's purpose is "ideas worth spreading". It let thousands of people
around the world run TEDx events themselves, none of them employed by TED.

What usually goes wrong: people write something that sounds good and that
nobody could possibly disagree with. If your purpose cannot be argued with, it
probably is not saying anything.""",
    },

    "staff-on-demand": {
        "body_he": """במקום להעסיק את כל מי שתצטרך אי פעם, הארגון שומר צוות
ליבה קטן ומצרף אנשים לפי העבודה שצריך לעשות עכשיו.

המנוף הוא מהירות, לא חיסכון. עובד קבוע הוא התחייבות של שנים לכישור מסוים,
וכישורים מתיישנים מהר מחוזי העסקה. צוות שנבנה לפי משימה יכול לשנות הרכב
בתוך שבועות במקום בתוך מחזור גיוס.

דוגמה: Gigwalk ו־Upwork בנו שכבה שלמה של עבודה לפי דרישה, ו־NASA משתמשת
בתחרויות פתוחות כדי לפתור בעיות הנדסיות שהצוות הפנימי נתקע בהן.

מה בדרך כלל משתבש: מפזרים החוצה בדיוק את הידע שאסור לאבד. את הליבה שמגדירה
מי אתם שומרים בפנים, ומרחיבים סביבה.""",
        "body_en": """Instead of hiring everyone you will ever need, the
organisation keeps a small core team and brings people in according to the work
that actually exists right now.

The leverage is speed, not saving money. A permanent hire is a multi-year
commitment to one particular skill, and skills go out of date faster than
employment contracts do. A team assembled per task can change shape in weeks
rather than in a hiring cycle.

Example: Gigwalk and Upwork built an entire layer of on-demand work, and NASA
runs open competitions to solve engineering problems its internal team is stuck
on.

What usually goes wrong: organisations push out exactly the knowledge they
cannot afford to lose. Keep the core that defines who you are inside, and
expand around it.""",
    },

    "community-and-crowd": {
        "body_he": """הקהילה היא האנשים שכבר אכפת להם ממה שאתם עושים. הקהל
הוא כל השאר, מי שאפשר להגיע אליו אבל עוד לא מכיר אתכם.

המנוף הוא שקהילה עושה דברים שאי אפשר לקנות: היא בודקת, מתקנת, מלמדת אנשים
חדשים, מתווכחת על הכיוון ומביאה את המשתמשים הבאים. עלות השיווק של ארגון עם
קהילה חיה נמוכה בסדר גודל מזו של מתחרה בלעדיה.

דוגמה: ויקיפדיה כתובה כמעט כולה בידי אנשים שלא מועסקים על ידה, ו־GitHub
הפך כל פרויקט קוד פתוח למקום שאפשר להצטרף אליו בלי לבקש רשות.

מה בדרך כלל משתבש: מתייחסים לקהילה כרשימת תפוצה. קהילה דורשת שתחזירו לה
ערך גם כשאתם לא מבקשים ממנה כלום.""",
        "body_en": """The community is the people who already care about what
you do. The crowd is everyone else, the people you can reach but who do not
know you yet.

The leverage is that a community does things you cannot buy: it tests, fixes,
teaches newcomers, argues about direction and brings in the next users.
Marketing costs an order of magnitude less for an organisation with a living
community than for a competitor without one.

Example: Wikipedia is written almost entirely by people it does not employ, and
GitHub turned every open source project into somewhere you can join without
asking permission.

What usually goes wrong: treating the community as a mailing list. A community
needs you to give it something back on the days you are not asking it for
anything.""",
    },

    "algorithms": {
        "body_he": """החלטות שנשענות על נתונים ומודלים, במקום על ישיבה שבה
האדם הבכיר בחדר מחליט.

המנוף הוא עקביות בקנה מידה. אדם טוב מקבל החלטה טובה, ואז צריך לישון.
אלגוריתם מקבל את אותה החלטה במיליון המקרים הבאים באותה איכות, בשלוש לפנות
בוקר, בלי להתעייף ובלי להעדיף את הלקוח שצעק הכי חזק.

דוגמה: ההמלצות של נטפליקס ותמחור הנסיעות של אובר הם המוצר עצמו, לא תוספת
לו. בלעדיהם אין שם עסק.

מה בדרך כלל משתבש: מפעילים אלגוריתם על נתונים שמשקפים את ההטיות של העבר,
ואז מתפלאים שהוא משחזר אותן. אלגוריתם מגדיל את מה שהאכלתם אותו, כולל את
הטעויות.""",
        "body_en": """Decisions made from data and models rather than in a
meeting where the most senior person in the room decides.

The leverage is consistency at scale. A good person makes a good decision, and
then has to sleep. An algorithm makes the same decision for the next million
cases at the same quality, at three in the morning, without getting tired and
without favouring whichever customer shouted loudest.

Example: Netflix's recommendations and Uber's pricing are the product itself,
not an addition to it. Without them there is no business there.

What usually goes wrong: running an algorithm on data that reflects the past's
biases, then being surprised when it reproduces them. An algorithm amplifies
whatever you fed it, mistakes included.""",
    },

    "leveraged-assets": {
        "body_he": """להשתמש בנכסים במקום להחזיק אותם: מחשוב, מפעלים, ציוד,
מחסנים ורכבים ששייכים למישהו אחר.

המנוף אינו רק חיסכון בהון. נכס שבבעלותכם הופך לדבר שצריך להצדיק, ומרגע
שקניתם מכונה תתחילו לחפש עבודה שתצדיק אותה. נכס שכור אפשר להפסיק לשכור
ביום שבו הכיוון משתנה.

דוגמה: אמזון שינתה את כלכלת התוכנה כשהפכה שרתים לשכירות לפי שעה. סטארטאפ
היום מתחיל בתשתית שפעם דרשה גיוס הון.

מה בדרך כלל משתבש: משכירים גם את הדבר שהוא היתרון התחרותי שלכם. אם זה מה
שמבדיל אתכם, זה צריך להיות שלכם.""",
        "body_en": """Use assets instead of owning them: computing, factories,
equipment, warehouses and vehicles that belong to someone else.

The leverage is not only saving capital. An asset you own becomes a thing that
has to be justified, and the moment you buy a machine you start looking for
work that justifies it. A rented asset can simply stop being rented on the day
the direction changes.

Example: Amazon changed the economics of software by turning servers into
something you rent by the hour. A startup today begins with infrastructure that
once required raising a funding round.

What usually goes wrong: renting the very thing that is your competitive
advantage. If it is what makes you different, it should be yours.""",
    },

    "engagement": {
        "body_he": """מנגנונים שגורמים לאנשים לחזור: משחוק, מוניטין, נקודות,
דירוגים, תחרויות והכרה פומבית.

המנוף הוא שהמעורבות מייצרת את הנתונים והקהילה שכל השאר נשען עליהם. משתמש
שחוזר מדי יום מלמד אתכם משהו בכל ביקור, ומשתמש שמדרג, מגיב או מדווח עושה
עבודה שאחרת הייתם צריכים לשלם עליה.

דוגמה: מערכות הדירוג ההדדי של איביי ו־Airbnb יצרו אמון בין זרים גמורים,
וזה מה שאפשר את העסק כולו.

מה בדרך כלל משתבש: מדביקים נקודות ותגים על מוצר שאנשים לא אוהבים. משחוק
לא מתקן חוויה גרועה, הוא רק מבליט אותה.""",
        "body_en": """Mechanisms that bring people back: gamification,
reputation, points, ratings, competitions and public recognition.

The leverage is that engagement produces the data and the community everything
else rests on. A user who returns daily teaches you something on every visit,
and a user who rates, comments or reports is doing work you would otherwise
have to pay for.

Example: eBay's and Airbnb's mutual rating systems created trust between
complete strangers, and that is what made the business possible at all.

What usually goes wrong: bolting points and badges onto a product people do not
enjoy. Gamification does not repair a bad experience, it only draws attention
to it.""",
    },

    "interfaces": {
        "body_he": """התהליכים והכלים שמחברים בין מה שקורה בחוץ, בקהילה
ובקהל, לבין הצוות הקטן שבפנים.

המנוף כאן פחות זוהר ויותר קריטי מכל השאר: בלי ממשק, כל מה שצומח בחוץ נוחת
כעבודה ידנית על שולחן של מישהו, והצוות הופך לצוואר בקבוק. ממשק טוב הופך
אלף פניות לתהליך אחד שרץ מעצמו.

דוגמה: מנגנון בדיקת האפליקציות של אפל מאפשר לצוות קטן לשמור על סטנדרט מול
מיליוני מפתחים, כי הבדיקה עצמה מאוטמטת ברובה.

מה בדרך כלל משתבש: בונים ממשק רק כשכבר טובעים. בשלב הזה הוא נבנה בחיפזון,
ומקבע את הכאוס במקום לפתור אותו.""",
        "body_en": """The processes and tools that connect what happens
outside, in the community and the crowd, to the small team on the inside.

The leverage here is less glamorous and more critical than any of the others:
without an interface, everything that grows outside lands as manual work on
somebody's desk, and the team becomes the bottleneck. A good interface turns a
thousand requests into one process that runs itself.

Example: Apple's app review lets a small team hold a standard against millions
of developers, because most of the checking is automated.

What usually goes wrong: building the interface only once you are already
drowning. At that point it gets built in a hurry, and it cements the chaos
instead of solving it.""",
    },

    "dashboards": {
        "body_he": """מדידה בזמן אמת של המספרים שבאמת משנים, זמינה לכל מי
שההחלטות שלו תלויות בהם.

המנוף הוא קצב הלמידה. ארגון שרואה את התוצאה של מהלך תוך יום יכול לנסות
חמישים מהלכים בשנה. ארגון שממתין לדוח הרבעוני יכול לנסות ארבעה. זה כל
ההבדל, והוא מצטבר.

דוגמה: שיטת ה־OKR שגוגל אימצה מאינטל הפכה מטרות לדבר שכל אחד בחברה יכול
לראות ולמדוד, ולא לשיחה שנתית עם המנהל.

מה בדרך כלל משתבש: מודדים את מה שקל לספור. מספר שעולה ולא משנה כלום גרוע
מאין מדידה, כי הוא מייצר ביטחון מזויף.""",
        "body_en": """Measuring the numbers that actually matter, in real time,
available to everyone whose decisions depend on them.

The leverage is the rate of learning. An organisation that sees the result of a
move within a day can try fifty moves a year. One that waits for the quarterly
report can try four. That is the whole difference, and it compounds.

Example: the OKR method Google adopted from Intel turned goals into something
anyone in the company can see and measure, rather than an annual conversation
with a manager.

What usually goes wrong: measuring what is easy to count. A number that goes up
and changes nothing is worse than no measurement, because it manufactures false
confidence.""",
    },

    "experimentation": {
        "body_he": """ניסויים קצרים ומבוקרים, בהנחה שרוב מה שאתם מאמינים בו
עכשיו שגוי במשהו.

המנוף הוא הורדת מחיר הטעות. ארגון שמנסה בקטן טועה בזול ומגלה מוקדם. ארגון
שמשיק פעם בשנה טועה ביוקר, ומגלה כשכבר אי אפשר לחזור אחורה.

דוגמה: מודל ה־Lean Startup הפך את זה לשיטה מסודרת, ואמזון מריצה אלפי
ניסויים בשנה על החנות עצמה.

מה בדרך כלל משתבש: מריצים ניסויים ואז מתעלמים מהתוצאה כשהיא לא נעימה.
ניסוי שהמסקנה שלו נקבעה מראש הוא רק בזבוז זמן מנומס.""",
        "body_en": """Short, controlled experiments, run on the assumption that
most of what you currently believe is wrong in some way.

The leverage is lowering the price of being wrong. An organisation that tries
things small is wrong cheaply and finds out early. One that launches once a year
is wrong expensively, and finds out when it is too late to turn around.

Example: the Lean Startup model made this into an orderly method, and Amazon
runs thousands of experiments a year on the store itself.

What usually goes wrong: running experiments and then ignoring the result when
it is unwelcome. An experiment whose conclusion was decided in advance is just
a polite waste of time.""",
    },

    "autonomy": {
        "body_he": """צוותים קטנים שמחליטים בעצמם, בלי לעבור דרך שרשרת אישורים
על כל צעד.

המנוף הוא זמן התגובה. בארגון היררכי, המרחק בין מי שרואה את הבעיה לבין מי
שמורשה לפתור אותה נמדד בשבועות. אוטונומיה מוחקת את המרחק הזה, ואיתו את
רוב ההזדמנויות שנעלמות בדרך.

דוגמה: Valve פועלת בלי מנהלים במובן הרגיל, ו־Spotify בנתה מבנה של צוותים
עצמאיים שכל אחד מהם אחראי לפיסת מוצר שלמה.

מה בדרך כלל משתבש: מבלבלים אוטונומיה עם היעדר כיוון. צוות אוטונומי צריך
מטרה חדה ומדידה ברורה, אחרת הוא רק מנותק.""",
        "body_en": """Small teams that decide for themselves, without routing
every step through a chain of approvals.

The leverage is response time. In a hierarchical organisation, the distance
between the person who sees the problem and the person allowed to fix it is
measured in weeks. Autonomy deletes that distance, and with it most of the
opportunities that disappear along the way.

Example: Valve operates without managers in the usual sense, and Spotify built
a structure of independent teams each owning a whole piece of the product.

What usually goes wrong: confusing autonomy with an absence of direction. An
autonomous team needs a sharp purpose and clear measurement, or it is simply
disconnected.""",
    },

    "social-technologies": {
        "body_he": """הכלים שמאפשרים לארגון לדבר עם עצמו: צ'אט, מסמכים
משותפים, ניהול משימות גלוי ווידאו.

המנוף הוא קיצור העיכוב בין שאלה לתשובה. כשהעיכוב הזה קטן, אפשר לעבוד
במקביל ובפיזור גאוגרפי בלי לאבד קצב. כשהוא גדול, כל החלטה ממתינה לפגישה
הבאה.

דוגמה: Slack ו־Notion הפכו את מצב הידע בארגון לדבר שניתן לחיפוש, במקום
משהו שיושב בתיבות דואר פרטיות.

מה בדרך כלל משתבש: מוסיפים עוד כלי לכל בעיה, עד שאף אחד לא יודע איפה
נמצאת התשובה. שלושה ערוצים שכולם עוקבים אחריהם עדיפים על עשרה שאיש לא
קורא.""",
        "body_en": """The tools that let an organisation talk to itself: chat,
shared documents, visible task management and video.

The leverage is shortening the delay between a question and an answer. When
that delay is small, people can work in parallel and in different places without
losing pace. When it is large, every decision waits for the next meeting.

Example: Slack and Notion turned an organisation's state of knowledge into
something searchable, rather than something sitting in private inboxes.

What usually goes wrong: adding another tool for every problem, until nobody
knows where the answer lives. Three channels everyone follows beat ten that
nobody reads.""",
    },

    "abundance-sources": {
        "body_he": """השאלה המעשית שמאחורי כל המנגנונים: מה כבר קיים בשפע
בעולם, ואתם יכולים להשתמש בו בלי לייצר אותו בעצמכם.

המנוף הוא שכל מה שהיה נדיר ויקר לפני עשור זמין היום כמעט בחינם. כוח מחשוב,
אחסון, הפצה, מודלים מאומנים, ידע פתוח וקהל שמוכן להשתתף. ארגון אקספוננציאלי
נבנה על השפע הזה במקום להילחם במחסור.

דוגמה: כל אפליקציה ניידת היום נשענת על GPS, מצלמה, תשלומים וזיהוי דיבור
שאיש מהמפתחים שלה לא בנה.

מה בדרך כלל משתבש: מייצרים בעצמכם דברים שכבר קיימים, מתוך הרגל או גאווה
מקצועית. זה זמן שנלקח מהדבר היחיד שרק אתם יכולים לבנות.""",
        "body_en": """The practical question behind all the mechanisms: what
already exists in abundance in the world that you can use without producing it
yourself?

The leverage is that almost everything that was scarce and expensive a decade
ago is now close to free. Computing power, storage, distribution, trained
models, open knowledge and an audience willing to take part. An exponential
organisation is built on that abundance instead of fighting scarcity.

Example: every mobile app today rests on GPS, a camera, payments and speech
recognition that none of its developers built.

What usually goes wrong: rebuilding things that already exist, out of habit or
professional pride. That is time taken from the one thing only you can build.""",
    },

    "launch-steps": {
        "body_he": """מה עושים ביום שאחרי הרעיון: הצעדים הקטנים והקונקרטיים
שאפשר להתחיל בהם בלי אישור, בלי תקציב ובלי לחכות לאף אחד.

המנוף הוא שהמרחק בין רעיון לבין הדבר הראשון שקיים במציאות הוא המקום שבו
רוב הרעיונות מתים. צעד שאפשר לעשות השבוע שווה יותר מתוכנית לשלוש שנים.

דוגמה: כמעט כל ארגון אקספוננציאלי התחיל מגרסה מביכה של עצמו. הראשונה לא
הייתה טובה, היא רק הייתה קיימת.

מה בדרך כלל משתבש: מנסחים צעד ראשון שדורש שלושה אישורים וחצי שנה. אם הצעד
הראשון לא מתחיל השבוע, הוא לא באמת צעד ראשון.""",
        "body_en": """What you do the day after the idea: the small, concrete
steps you can start on without approval, without a budget and without waiting
for anyone.

The leverage is that the distance between an idea and the first thing that
actually exists is where most ideas die. A step you can take this week is worth
more than a three-year plan.

Example: nearly every exponential organisation started as an embarrassing
version of itself. The first one was not good, it was just real.

What usually goes wrong: writing a first step that needs three approvals and
six months. If the first step does not start this week, it is not really a
first step.""",
    },
}
