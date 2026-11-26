"""One-time import of Avi's reference site into the database
(docs/academia360/data_model.md section 11; building_an_app.md "seeding is
one-time only").

    manage.py import_reference [--root PATH] [--dry-run]

Idempotent: every row is found before it is made, and an existing row is left
alone, so a person's later edit in the app survives any re-run. Files are
copied into private storage only when their row is created. The run is
recorded as one AgentRun (actor: import). Whatever could not be read cleanly
is reported, not guessed.

The reference folder is confidential and git-ignored; on a machine without it
the command says so and does nothing.
"""

import csv
import json
import re
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from academia360 import xlsx
from academia360.models import (
    AcademicYear,
    AgentRun,
    Allocation,
    Analysis,
    Collaboration,
    ContactPerson,
    Criterion,
    CriterionFinding,
    GuidelineSection,
    Institution,
    InstitutionMetric,
    KpiDefinition,
    KpiValue,
    Participation,
    ProfileSection,
    Program,
    ResearchCenter,
    Researcher,
    ResearcherLink,
    ResearcherMetric,
    ResponseLetter,
    ReviewQuestion,
    StudyProgram,
    Submission,
    SubmittedFile,
    TimelineEvent,
    Unit,
)

DEFAULT_ROOT = Path(settings.BASE_DIR) / "docs" / "academia360" / "reference" / "Academia360"

YEARS = [("תשפ״ד", 2023, 2024), ("תשפ״ה", 2024, 2025), ("תשפ״ו", 2025, 2026), ("תשפ״ז", 2026, 2027),
         ("תשפ״ח", 2027, 2028)]

# The five headline criteria (coloured: they are the 360 ring) and the review
# form's further domains, in the committee's order.
CRITERIA = [
    ("formal", "עמידה בדרישות פורמליות", ""),
    ("institutional", "אסטרטגיה מוסדית ומחויבות הנהלה", "#8FC457"),
    ("twenty", "עמידה ביעד 20%", ""),
    ("standard", "תו התקן", ""),
    ("innovation", "חדשנות בהוראה", "#63BAC5"),
    ("employability", "תעסוקתיות", "#F6C21A"),
    ("community", "מעורבות חברה וקהילה", "#EE6B67"),
    ("faculty", "עידוד מצוינות והכשרות לסגל", ""),
    ("additional", "רכיבים נוספים", ""),
    ("management", "ניהול ותקצוב", ""),
    ("measurement", "מדדי ביצוע והערכת תוצאות", "#323435"),
]
DOMAIN_TO_SLUG = {name: slug for slug, name, _c in CRITERIA}
DOMAIN_TO_SLUG.update({"מעורבות חברתית/קהילתית": "community", "מדיניות מוסדית": "institutional",
                       "יכולת מדידה והערכה": "measurement"})  # the guidelines' table names them so
DOMAIN_TO_SLUG.update({"אסטרטגיה מוסדית": "institutional", "מעורבות חברה וקהילה": "community",
                       "חדשנות בהוראה": "innovation", "תעסוקתיות": "employability",
                       "מדדי ביצוע והערכת תוצאות": "measurement", "ניהול ותקצוב": "management",
                       "עידוד מצויינות והכשרות לסגל": "faculty", "סיכום": None})
ALIGNMENT_KEYS = {"innovation": "innovation", "employability": "employability", "community": "community",
                  "institutional": "institutional", "measurement": "measurement"}

MANDATORY_KPIS = [
    ("מספר תכניות הלימוד לתואר ראשון שעודכנו", "על פי תו התקן המוסדי"),
    ("מספר הסטודנטים לתואר ראשון בתכניות הלימוד/אשכולות שעודכנו", "על פי תו התקן המוסדי"),
    ("מספר הסטודנטים שעשו התנסות כחלק מתוכנית הלימודים", "בהיקף של לפחות 100 שעות"),
    ("מספר קורסים שמלמדים מרצים עם קשר למגזרים העסקי/הציבורי/השלישי", ""),
    ("מספר הסטודנטים שמשתתפים בפרויקטים חברתיים/קורסי מעורבות אקדמית בקהילה", "המעניקים נ״ז אקדמיות"),
]
KPI_HEADER_YEARS = {"מצב נוכחי": ("תשפ״ה", "baseline"), "תשפ\"ו": ("תשפ״ו", "forecast"),
                    "תשפ\"ז": ("תשפ״ז", "forecast"), "תשפ\"ח": ("תשפ״ח", "forecast")}

# Proposal folders that the institutions list does not cover.
EXTRA_FOLDERS = {
    "אחוה": ("המכללה האקדמית אחוה", "Achva Academic College", "achva", Institution.COLLEGE),
    "הדסה": ("המכללה האקדמית הדסה", "Hadassah Academic College", "hadassah", Institution.COLLEGE),
    "גליל מערבי": ("המכללה האקדמית גליל מערבי", "Western Galilee College", "western-galilee", Institution.COLLEGE),
    "האקדמיה למוסיקה": ("האקדמיה למוסיקה ולמחול בירושלים", "Jerusalem Academy of Music and Dance", "jamd",
                        Institution.COLLEGE),
}
# Letter and sheet names that spell an institution differently from its row.
LETTER_ALIASES = {"לוינסקי": "לוינסקי-ויניצקי", "מוסיקה ומחול": "האקדמיה למוסיקה ולמחול בירושלים",
                  "מכון לב": "המכון האקדמי לב ירושלים", "סמי שמעון": "המכון הטכנולוגי להנדסה - באר שבע",
                  "בן גוריון": "בן-גוריון", "בר אילן": "בר-אילן", "תל חי": "תל-חי"}
KIND_MAP = {"university": Institution.UNIVERSITY, "academic_college": Institution.COLLEGE,
            "teacher_training": Institution.TEACHER, "research_institute": Institution.RESEARCH}
FILE_KINDS = [("מדדי", "annex_a"), ("נספח א", "annex_a"), ("תקציב", "annex_b"), ("נספח ב", "annex_b"),
              ("התחייבות", "commitment"), ("הצהרה", "declaration"), ("חתום", "signature"), ("חתימה", "signature"),
              ("מכתב", "cover_letter"), ("דוח ביצוע", "report"), ("מחקר", "research"), ("דוח", "research"),
              ("פרופיל", "research"), ("דו״ח", "research"), ('דו"ח', "research")]


def _norm(s):
    return re.sub(r"[\s\-–־'\"״׳().,:]+", "", (s or "").replace("אוניברסיטת", "").replace("המכללה האקדמית", "")
                  .replace("המרכז האקדמי", "").replace("מכללת", ""))


class Command(BaseCommand):
    help = "One-time, idempotent import of the reference site into Academia360's tables."

    def add_arguments(self, parser):
        parser.add_argument("--root", default=str(DEFAULT_ROOT))
        parser.add_argument("--dry-run", action="store_true")

    # ------------------------------------------------------------ helpers

    def made(self, what, created):
        self.counts.setdefault(what, [0, 0])
        self.counts[what][0 if created else 1] += 1

    def report(self, line):
        self.notes.append(line)
        self.stdout.write(line)

    def get_or_create(self, model, defaults=None, **keys):
        if self.dry:
            obj = model.objects.filter(**keys).first()
            self.made(model.__name__, obj is None)
            return obj, obj is None
        obj, created = model.objects.get_or_create(defaults=defaults or {}, **keys)
        self.made(model.__name__, created)
        return obj, created

    # --------------------------------------------------------------- run

    def handle(self, *args, **options):
        self.root = Path(options["root"])
        self.dry = options["dry_run"]
        self.counts, self.notes = {}, []
        if not (self.root / "data" / "institutions.json").exists():
            self.stdout.write(f"no reference at {self.root}; nothing imported")
            return
        self.program = self.import_program()
        self.years = {y.hebrew_name: y for y in AcademicYear.objects.filter(program=self.program)}
        self.criteria = {c.slug: c for c in Criterion.objects.filter(program=self.program)}
        self.import_review_form()
        self.import_mandatory_kpis()
        self.import_guidelines()
        self.import_criterion_descriptions()
        self.institutions = {}
        self.import_institutions()
        self.import_extra_folders()
        self.import_tracking_sheet()
        for inst, folder in self.folders.items():
            self.import_structured(inst, folder)
            self.import_csvs(inst, folder)
            self.import_kpi_sheet(inst, folder)
            self.import_html(inst, folder)
        self.import_letters()
        total = sum(c[0] for c in self.counts.values())
        if not self.dry:
            AgentRun.objects.create(purpose="import_reference", sources=str(self.root), rows_touched=total,
                                    notes="\n".join(self.notes)[:20000], finished_at=_now())
        for name, (created, left) in sorted(self.counts.items()):
            self.stdout.write(f"{name:24} added {created:5}  left alone {left:5}")
        self.stdout.write(f"done: {total} rows added, {sum(c[1] for c in self.counts.values())} left alone")

    # ------------------------------------------------------------ program

    def import_program(self):
        program, _ = self.get_or_create(Program, slug="academia-360", defaults=dict(
            name="אקדמיה 360", short_name="אקדמיה 360", body="ות״ת / מל״ג", year_from=2024, year_to=2028,
            total_budget_nis=200_000_000, status="running",
            official_url="https://che.org.il/decision/תכנית-ותת-לקידום-שינויי-עומק-בתוכניות/",
            description=("אקדמיה 360 מזמינה כל מוסד מתוקצב להשכלה גבוהה לבנות אסטרטגיה רב־שנתית לעדכון "
                         "תכניות הלימוד לתואר ראשון: הוראה חדשנית, תעסוקתיות הבוגרים, ומעורבות בחברה "
                         "ובקהילה. האתר הזה אוסף את התכנית, את המוסדות ואת מה שכל אחד מהם הציע, במקום "
                         "אחד, בשפה פשוטה.")))
        if program is None:
            return None
        for i, (he, a, b) in enumerate(YEARS):
            self.get_or_create(AcademicYear, program=program, hebrew_name=he,
                               defaults=dict(gregorian_from=a, gregorian_to=b, order=i))
        for i, (slug, name, colour) in enumerate(CRITERIA):
            self.get_or_create(Criterion, program=program, slug=slug, defaults=dict(name=name, order=i, colour=colour))
        return program

    def import_review_form(self):
        path = self.root / "documents" / "proposals" / "חלוקה לחברי הוועדה ופורמט לבדיקה  מעודכן.xlsx"
        if not path.exists():
            return self.report("review form: sheet not found, questions not imported")
        rows = xlsx.sheets(path).get("פורמט לבדיקת תכניות", [])
        current, order = None, 0
        d_col, q_col = 0, 1
        for row in rows:  # the header names the columns; the sheet has empty leading ones
            texts = [xlsx.text(c) for c in row]
            if "תחום" in texts and "שאלה/הנחיה" in texts:
                d_col, q_col = texts.index("תחום"), texts.index("שאלה/הנחיה")
                break
        for row in rows:
            cells = [xlsx.text(c) for c in row] + [""] * (q_col + 2)
            domain, question = cells[d_col], cells[q_col]
            if domain and domain in DOMAIN_TO_SLUG:
                slug = DOMAIN_TO_SLUG[domain]
                current = self.criteria.get(slug) if slug else None
                order = 0
            if current is None or not question or question in ("שאלה/הנחיה",):
                continue
            order += 1
            self.get_or_create(ReviewQuestion, criterion=current, text=question, defaults=dict(order=order))

    def import_mandatory_kpis(self):
        for i, (name, how) in enumerate(MANDATORY_KPIS):
            self.get_or_create(KpiDefinition, program=self.program, submission=None, name=name,
                               defaults=dict(is_mandatory=True, order=i, how_measured=how))

    def import_guidelines(self):
        path = self.root / "Academia360_Guidelines.md"
        if not path.exists():
            return
        body = path.read_text(encoding="utf-8")
        parts = re.split(r"^## ", body, flags=re.M)
        for i, part in enumerate(parts[1:]):
            title, _, text = part.partition("\n")
            self.get_or_create(GuidelineSection, program=self.program, title=title.strip(),
                               defaults=dict(body=text.strip(), order=i))

    def import_criterion_descriptions(self):
        """The guidelines' criteria table describes each domain in a line; a
        criterion whose description is still empty takes it. Never overwrites,
        so an edit made in the app survives the next run."""
        for sec in GuidelineSection.objects.filter(program=self.program, title__contains="קריטריונים"):
            for line in sec.body.splitlines():
                cells = [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]
                if len(cells) < 2 or cells[0] not in DOMAIN_TO_SLUG or not cells[1]:
                    continue
                crit = self.criteria.get(DOMAIN_TO_SLUG[cells[0]])
                if crit is not None and not crit.description and not self.dry:
                    crit.description = cells[1]
                    crit.save(update_fields=["description"])

    # -------------------------------------------------------- institutions

    def _institution(self, raw):
        slug = slugify(raw.get("nameEn") or "", allow_unicode=False) or f"inst-{raw['id']}"
        slug = slug[:50]
        inst, created = self.get_or_create(Institution, slug=slug, defaults=dict(
            name_he=raw["nameHe"], name_en=raw.get("nameEn") or "", kind=KIND_MAP.get(raw.get("type"), Institution.COLLEGE),
            city=raw.get("location") or "", website=raw.get("website") or "",
            short_name_he=_short(raw["nameHe"])))
        return inst

    def import_institutions(self):
        data = json.loads((self.root / "data" / "institutions.json").read_text(encoding="utf-8-sig"))
        self.folders = {}
        for raw in data["institutions"]:
            inst = self._institution(raw)
            if inst is None:
                continue
            self.institutions[_norm(raw["nameHe"])] = inst
            applied = bool(raw.get("proposalSubmitted"))
            part, _ = self.get_or_create(Participation, program=self.program, institution=inst, defaults=dict(
                applied=applied, status="responded" if applied else "did_not_apply",
                first_submitted_at=_month(raw.get("submissionDate"))))
            if part is None:
                continue
            contact = raw.get("contactPerson") or {}
            if contact.get("name"):
                self.get_or_create(ContactPerson, participation=part, name=_clean(contact["name"]), defaults=dict(
                    title=_clean(contact.get("role") or ""), email=contact.get("email") or "",
                    phone=contact.get("phone") or "", is_primary=True))
            folder = raw.get("proposalFolder")
            if applied and folder:
                self.folders[inst] = self.root / folder
                sub = self._proposal(part, raw.get("submissionDate"))
                for name in raw.get("proposalFiles") or []:
                    self._file(sub, self.root / folder / name)
                self._analysis(sub, raw.get("programAlignment"))

    def import_extra_folders(self):
        base = self.root / "documents" / "proposals"
        for folder_name, (he, en, slug, kind) in EXTRA_FOLDERS.items():
            folder = base / folder_name
            if not folder.is_dir():
                continue
            inst, _ = self.get_or_create(Institution, slug=slug, defaults=dict(
                name_he=he, name_en=en, kind=kind, short_name_he=_short(he)))
            if inst is None:
                continue
            self.institutions[_norm(he)] = inst
            part, _ = self.get_or_create(Participation, program=self.program, institution=inst,
                                         defaults=dict(applied=True, status="responded"))
            if part is None:
                continue
            self.folders[inst] = folder
            sub = self._proposal(part, None)
            for path in sorted(folder.iterdir()):
                if path.suffix.lower() in (".pdf", ".docx", ".xlsx", ".ods"):
                    self._file(sub, path)

    def _proposal(self, part, when):
        sub, _ = self.get_or_create(Submission, participation=part, kind="proposal", defaults=dict(
            status="responded", submitted_at=_month(when) or part.first_submitted_at,
            academic_year=self.years.get("תשפ״ה")))
        return sub

    def _file(self, sub, path):
        if sub is None or not path.exists() or path.is_dir():
            if sub is not None and not path.exists():
                self.report(f"missing file: {path.name}")
            return
        if path.suffix.lower() in (".html", ".md", ".json", ".csv"):
            return  # the site's own pages and data, not what the institution sent
        kind = next((k for needle, k in FILE_KINDS if needle in path.name), "plan")
        if kind == "research" and "דוח ביצוע" not in path.name:
            kind = "research"
        row = SubmittedFile.objects.filter(submission=sub, original_name=path.name).first()
        if row is not None:
            self.made("SubmittedFile", False)
            return
        self.made("SubmittedFile", True)
        if self.dry:
            return
        with path.open("rb") as fh:
            row = SubmittedFile(submission=sub, kind=kind, original_name=path.name, size=path.stat().st_size)
            row.file.save(_safe_name(path.name), File(fh), save=True)

    def _analysis(self, sub, alignment):
        if sub is None or not alignment:
            return
        analysis, created = self.get_or_create(Analysis, submission=sub, defaults=dict(
            summary=alignment.get("summary") or "", confirmed=False))
        if analysis is None or not created:
            return
        order = 0
        for key, text in (alignment.get("criteria") or {}).items():
            crit = self.criteria.get(ALIGNMENT_KEYS.get(key))
            order += 1
            self.get_or_create(CriterionFinding, analysis=analysis, criterion=crit, kind="finding", text=text,
                               defaults=dict(order=order))
        for kind, items in (("strength", alignment.get("strengths")), ("challenge", alignment.get("challenges"))):
            for text in items or []:
                order += 1
                self.get_or_create(CriterionFinding, analysis=analysis, kind=kind, text=text, defaults=dict(order=order))

    # --------------------------------------------------- the tracking sheet

    def import_tracking_sheet(self):
        path = self.root / "documents" / "proposals" / "מעקב הגשות 360.xlsx"
        if not path.exists():
            return
        rows = next(iter(xlsx.sheets(path).values()), [])
        matched = 0
        for row in rows[1:]:
            cells = list(row) + [None] * 9
            name = xlsx.text(cells[0])
            inst = self._match(name)
            if inst is None:
                continue
            matched += 1
            self.get_or_create(Allocation, program=self.program, institution=inst, defaults=dict(
                undergrad_students=_int(cells[1]), approved_programs=_int(cells[2]),
                allocation_thousands_nis=_int(cells[3]), notes=xlsx.text(cells[8])))
        self.report(f"tracking sheet: {matched} institutions matched")

    def _match(self, name):
        for needle, alias in LETTER_ALIASES.items():
            if needle in name:
                name = alias
                break
        key = _norm(name)
        if not key:
            return None
        if key in self.institutions:
            return self.institutions[key]
        for k, inst in self.institutions.items():
            if k and (k in key or key in k):
                return inst
        return None

    # ------------------------------------------- per-institution structured

    def import_structured(self, inst, folder):
        path = folder / "data_structured.json"
        if not path.exists():
            return
        try:
            d = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            return self.report(f"{inst}: data_structured.json unreadable ({exc})")
        if not isinstance(d, dict):
            return self.report(f"{inst}: data_structured.json is not an object")
        as_of = _date(d.get("snapshot_date"))
        overview = _d(d.get("overview"))
        if not self.dry and not inst.identity and overview.get("unique_identity"):
            inst.identity = str(overview["unique_identity"])[:2000]
            inst.founded = inst.founded or _int(overview.get("founded"))
            inst.save(update_fields=["identity", "founded"])
        for p in _dicts(d.get("programs")):
            unit = None
            if p.get("unit"):
                unit, _ = self.get_or_create(Unit, institution=inst, name=str(p["unit"])[:200])
            if p.get("name"):
                self.get_or_create(StudyProgram, institution=inst, name=str(p["name"])[:200], defaults=dict(unit=unit))
        enrol = _d(d.get("enrollment"))
        for level, value in _d(enrol.get("by_level")).items():
            if _num(value) is not None:
                self.get_or_create(InstitutionMetric, institution=inst, key=f"students_{level}", year=None,
                                   defaults=dict(value=_num(value), unit="headcount", source="research report",
                                                 as_of=as_of))
        for point in _dicts(enrol.get("trend")):
            if _num(point.get("total")) is not None and _int(point.get("year")):
                self.get_or_create(InstitutionMetric, institution=inst, key="students_total", year=_int(point["year"]),
                                   defaults=dict(value=_num(point["total"]), unit="headcount",
                                                 source="research report", as_of=as_of))
        faculty = _d(d.get("faculty"))
        if _num(faculty.get("total")) is not None:
            self.get_or_create(InstitutionMetric, institution=inst, key="faculty_total", year=None,
                               defaults=dict(value=_num(faculty["total"]), unit="headcount", source="research report",
                                             as_of=as_of))
        research = _d(d.get("research"))
        for i, c in enumerate(_dicts(research.get("centers"))):
            if c.get("name"):
                self.get_or_create(ResearchCenter, institution=inst, name=str(c["name"])[:200], defaults=dict(
                    full_name=str(c.get("name_full") or "")[:300], founded=_int(c.get("founded")),
                    focus=str(c.get("focus") or ""), equipment=str(c.get("equipment") or ""),
                    partners=_join(c.get("partners")), order=i))
        for prof in _dicts(research.get("top_professors")):
            self._researcher(inst, prof.get("name"), unit=prof.get("unit"), areas=_join(prof.get("areas")),
                             h_index=prof.get("h_index"), citations=prof.get("citations"),
                             profiles=prof.get("profiles"), as_of=as_of, leading=True)
        for r in _dicts(_d(d.get("ai")).get("top_researchers")):
            self._researcher(inst, r.get("name"), areas=_join(r.get("focus")), h_index=r.get("h_index"),
                             kind=r.get("type"), as_of=as_of, leading=True)
        for kind, partners in _d(d.get("collaborations")).items():
            if kind not in ("academic", "industry", "government", "community"):
                continue
            for partner in (partners if isinstance(partners, list) else []):
                if isinstance(partner, str) and partner.strip():
                    self.get_or_create(Collaboration, institution=inst, kind=kind, partner=partner.strip()[:200])

    def _researcher(self, inst, name, unit=None, areas="", h_index=None, citations=None, profiles=None, as_of=None,
                    kind=None, leading=False):
        name = _clean(name or "")
        if not name:
            return
        slug = slugify(name, allow_unicode=True)[:50] or f"r{abs(hash(name)) % 10**6}"
        unit_row = None
        if unit:
            unit_row, _ = self.get_or_create(Unit, institution=inst, name=str(unit)[:200])
        title, bare = _split_title(name)
        row, created = self.get_or_create(Researcher, institution=inst, slug=slug, defaults=dict(
            name_he=bare if _is_hebrew(bare) else "", name_en="" if _is_hebrew(bare) else bare, title=title,
            areas=(areas or "")[:300], unit=unit_row, is_leading=leading,
            kind={"algorithmic": "algorithmic", "applied": "applied"}.get(str(kind or "").lower(), "other")))
        if row is None:
            return
        if not row.name_he:  # English only; show the English name in the Hebrew slot rather than nothing
            if not self.dry:
                row.name_he = row.name_en
                row.save(update_fields=["name_he"])
        for metric, value in (("h_index", h_index), ("citations", citations)):
            n = _num(value)
            if n is not None:
                self.get_or_create(ResearcherMetric, researcher=row, metric=metric, as_of=as_of, defaults=dict(
                    value=int(n), approximate=str(value).strip().startswith(("~", "≈")), source="reference"))
        for kind_, url in _profile_links(profiles):
            self.get_or_create(ResearcherLink, researcher=row, kind=kind_, url=url)

    def import_csvs(self, inst, folder):
        path = folder / "data_ai_researchers.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    value = r.get("metric_value")
                    self._researcher(inst, r.get("name"), unit=r.get("school_or_faculty"), areas=r.get("ai_focus"),
                                     h_index=value if (r.get("metric_type") or "") == "h_index" else None,
                                     citations=value if (r.get("metric_type") or "") == "citations" else None,
                                     profiles=r.get("profiles"), as_of=_date(r.get("metric_as_of")), leading=True)
        for name in ("data_enrollment_departments.csv", "data_enrollment_faculty.csv"):
            path = folder / name
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    if (r.get("unit_type") or "") != "institution" or _num(r.get("value")) is None:
                        continue
                    self.get_or_create(InstitutionMetric, institution=inst, key=(r.get("metric") or "value")[:60],
                                       year=_int(r.get("year")), defaults=dict(
                                           value=_num(r["value"]), unit=(r.get("unit") or "")[:30],
                                           source=(r.get("source") or "")[:200], source_url=_url(r.get("url")),
                                           as_of=_date(r.get("as_of"))))

    def import_kpi_sheet(self, inst, folder):
        sheet_path = next((p for p in folder.glob("*.xlsx") if "מדד" in p.name), None)
        if sheet_path is None:
            return
        try:
            book = xlsx.sheets(sheet_path)
        except Exception as exc:  # a broken workbook is reported, not fatal
            return self.report(f"{inst}: KPI sheet unreadable ({exc})")
        rows = book.get("מדדים") or next(iter(book.values()), [])
        header, name_col, year_cols = None, None, {}
        for r_i, row in enumerate(rows):
            texts = [xlsx.text(c) for c in row]
            if any("מדד ההצלחה" in t for t in texts):
                header = r_i
                for c_i, t in enumerate(texts):
                    if "מדד ההצלחה" in t:
                        name_col = c_i
                    for needle, (year, kind) in KPI_HEADER_YEARS.items():
                        if needle in t.replace("״", '"'):
                            year_cols[c_i] = (year, kind)
                break
        if header is None or name_col is None or not year_cols:
            return self.report(f"{inst}: KPI sheet has no recognisable header")
        part = Participation.objects.filter(program=self.program, institution=inst).first()
        sub = Submission.objects.filter(participation=part, kind="proposal").first() if part else None
        if part is None or sub is None:
            return
        mandatory = {_norm(n): n for n, _h in MANDATORY_KPIS}
        made = 0
        for row in rows[header + 1:]:
            cells = list(row) + [None] * (max(year_cols) + 2)
            name = xlsx.text(cells[name_col])
            if not name or len(name) < 6 or name.startswith(("נספח", "שם המוסד", "מספר תכניות לימוד", "מספר סטודנטים לתואר")):
                continue
            key = _norm(name)
            canonical = next((v for k, v in mandatory.items() if k and (k in key or key in k)), None)
            if canonical:
                kpi = KpiDefinition.objects.filter(program=self.program, is_mandatory=True, name=canonical).first()
            else:
                kpi, _ = self.get_or_create(KpiDefinition, program=self.program, submission=sub, name=name[:300],
                                            defaults=dict(is_mandatory=False, explanation=xlsx.text(cells[name_col + 1])[:2000],
                                                          how_measured=xlsx.text(cells[name_col + 2])[:2000]))
            if kpi is None:
                continue
            for c_i, (year, kind) in year_cols.items():
                raw = cells[c_i]
                n = xlsx.number(raw)
                txt = xlsx.text(raw)
                if n is None and not txt:
                    continue
                year_row = self.years.get(year)
                if year_row is None:
                    continue
                self.get_or_create(KpiValue, kpi=kpi, participation=part, academic_year=year_row, kind=kind,
                                   defaults=dict(value=n, text_value="" if n is not None else txt[:200], reported_in=sub))
                made += 1
        self.report(f"{inst}: KPI sheet read, {made} values")

    # --------------------------------------- the site's own pages (HTML)

    SECTION_KINDS = [("סקירה", "overview"), ("מצוינות מחקרית", "research"), ("מחקר", "research"),
                     ("יזמות", "innovation"), ("חדשנות", "innovation"), ("דירוג", "rankings")]
    SKIP_SECTIONS = ("רוצים לגלות", "סטטיסטיקות", "התפלגות", "קישורים", "מקורות")

    def import_html(self, inst, folder):
        """The researchers and overview pages Avi's site generated per
        institution: names, units, h-index, verified-looking links, the
        overview's sections and its timeline. Best effort, never a guess:
        what the page does not say stays empty."""
        as_of = date(2025, 10, 1)
        for name in ("researchers.html", "leading_researchers.html"):
            path = folder / name
            if not path.exists():
                continue
            html = path.read_text(encoding="utf-8", errors="replace")
            for block in re.split(r'class="(?:researcher-card|research-card)"', html)[1:]:
                head = re.search(r"<h[23][^>]*>(.*?)</h[23]>", block, re.S)
                if not head:
                    continue
                person = _strip(re.sub(r"<span[^>]*>.*?</span>", "", head.group(1), flags=re.S))
                if not person or len(person) > 80:
                    continue
                title_div = re.search(r'class="title"[^>]*>(.*?)</div>', block, re.S)
                unit = _strip(title_div.group(1)).split("|")[0].split("•")[0].strip()[:200] if title_div else ""
                focus_div = re.search(r'class="focus"[^>]*>(.*?)</div>', block, re.S)
                areas = _strip(focus_div.group(1))[:300] if focus_div else ""
                h = re.search(r"[Hh]-?index:?\s*(~?≈?\d+)", block)
                cites = re.search(r"([\d,]{4,})\+?\s*ציטוטים", block)
                links = {}
                for href in re.findall(r'href="(https?://[^"]+)"', block):
                    low = href.lower()
                    if re.search(r"user=[A-Z]{4,}", href) or "TBD" in href:
                        continue  # the site's own placeholders
                    kind = ("scholar" if "scholar.google" in low else "orcid" if "orcid.org" in low
                            else "dblp" if "dblp" in low else None)
                    if kind and kind not in links:
                        links[kind] = href
                self._researcher(inst, person, unit=unit or None, areas=areas,
                                 h_index=h.group(1) if h else None, citations=cites.group(1) if cites else None,
                                 profiles={k: v for k, v in links.items()}, as_of=as_of, leading=True)
        path = folder / "index.html"
        if not path.exists():
            return
        html = path.read_text(encoding="utf-8", errors="replace")
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S)
        heads = list(re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.S))
        order = 0
        for i, m in enumerate(heads):
            title = re.sub(r"[^\w\s֐-׿,.:'\"()-]", "", _strip(m.group(1))).strip()
            if not title or any(skip in title for skip in self.SKIP_SECTIONS):
                continue
            end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
            chunk = body[m.end():end]
            if "timeline-item" in chunk:
                for item in re.findall(r'class="timeline-item"[^>]*>(.*?)</div>\s*</div>', chunk, re.S):
                    year = re.search(r'class="year"[^>]*>(.*?)</div>', item, re.S)
                    event = re.search(r'class="event"[^>]*>(.*?)</div>', item, re.S)
                    y = _int(_strip(year.group(1))) if year else None
                    if y and event:
                        self.get_or_create(TimelineEvent, institution=inst, year=y, text=_strip(event.group(1))[:300])
                continue
            text = _paragraphs(chunk)
            if len(text) < 80:
                continue
            kind = next((k for needle, k in self.SECTION_KINDS if needle in title), "other")
            order += 1
            self.get_or_create(ProfileSection, institution=inst, title=title[:200], defaults=dict(
                kind=kind, body=text[:6000], order=order, source="אתר הרפרנס של אבי, אוקטובר 2025", as_of=as_of))

    # ------------------------------------------------------------- letters

    def import_letters(self):
        base = self.root / "documents" / "responses"
        if not base.is_dir():
            return
        for path in sorted(base.glob("*.pdf")):
            inst = self._match(path.stem)
            if inst is None:
                self.report(f"letter without a matching institution: {path.name}")
                continue
            part = Participation.objects.filter(program=self.program, institution=inst).first()
            sub = Submission.objects.filter(participation=part, kind="proposal").first() if part else None
            if sub is None:
                self.report(f"letter for an institution without a proposal, kept as file only later: {path.name}")
                continue
            existing = ResponseLetter.objects.filter(submission=sub).first()
            if existing is not None:
                self.made("ResponseLetter", False)
                continue
            self.made("ResponseLetter", True)
            if self.dry:
                continue
            with path.open("rb") as fh:
                letter = ResponseLetter(submission=sub, sent_at=date(2025, 4, 1))
                letter.file.save(_safe_name(path.name), File(fh), save=True)


# ------------------------------------------------------------------ utils

def _now():
    from django.utils import timezone
    return timezone.now()


def _short(name):
    name = name.replace(" – ", "–")
    for prefix in ("המכללה האקדמית להנדסה ", "המכללה האקדמית לחינוך ", "המכללה האקדמית ", "המרכז האקדמי ", "מכללת "):
        if name.startswith(prefix):
            return name[len(prefix):].split(" - ")[0][:80]
    return name.split("–")[0].split(" - ")[0].strip()[:80]


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _month(s):
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})", str(s))
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


def _date(s):
    if not s:
        return None
    s = str(s)
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", s)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3) or 1) <= 31:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
        except ValueError:
            pass
    m = re.match(r"(\d{4})", s)
    return date(int(m.group(1)), 1, 1) if m else None


def _int(v):
    n = _num(v)
    return int(n) if n is not None else None


def _num(v):
    if v is None or isinstance(v, (dict, list)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("+", "").replace("~", "").replace("≈", "").strip()
    m = re.match(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _d(v):
    return v if isinstance(v, dict) else {}


def _dicts(seq):
    return [x for x in (seq if isinstance(seq, list) else []) if isinstance(x, dict)]


def _join(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v or "")


def _url(v):
    v = str(v or "").strip()
    return v if v.startswith("http") else ""


def _safe_name(name):
    stem, dot, ext = name.rpartition(".")
    return (slugify(stem, allow_unicode=True)[:80] or "file") + (dot + ext.lower() if dot else "")


def _strip(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def _paragraphs(chunk):
    """Block text out of a page fragment, one paragraph per block element."""
    chunk = re.sub(r"<(p|li|h3|h4|div)[^>]*>", " ¶ ", chunk)
    text = _strip(chunk)
    parts = [p.strip() for p in text.split("¶")]
    out, seen = [], set()
    for p in parts:
        if len(p) > 25 and p not in seen:
            seen.add(p)
            out.append(p)
    return "\n\n".join(out)


def _is_hebrew(s):
    return bool(re.search(r"[֐-׿]", s or ""))


def _split_title(name):
    for t in ("פרופ'", "פרופ׳", "פרופ", "ד\"ר", "ד״ר", "Prof.", "Dr.", "Prof", "Dr"):
        if name.startswith(t + " ") or name.startswith(t + "' "):
            return t.rstrip("."), name[len(t):].lstrip("'. ").strip()
    return "", name


def _profile_links(profiles):
    out = []
    if isinstance(profiles, dict):
        items = profiles.items()
    elif isinstance(profiles, str):
        items = [(p.strip(), "") for p in profiles.split(";")]
    elif isinstance(profiles, list):
        items = [(str(p), "") for p in profiles]
    else:
        return out
    for key, val in items:
        key_l = str(key).lower()
        url = val if str(val).startswith("http") else (key if str(key).startswith("http") else "")
        if not url:
            continue
        kind = "scholar" if "scholar" in key_l or "scholar" in url else "orcid" if "orcid" in key_l or "orcid" in url \
            else "dblp" if "dblp" in key_l or "dblp" in url else "homepage"
        out.append((kind, url))
    return out
