"""Build usa-2026-items.json — the rich per-item data behind the itinerary
detail pages — from a saved copy of the source plan page.

Run from the repo root:  python docs/ustrip/trip-data/build_items_json.py

Two layers, on purpose:

1. Mechanical (never hand-edited): every <li> in the source's day-by-day
   timeline (source/daily-plan.html, a snapshot of
   https://avisalmon.github.io/arhab/pages/daily-plan.html) parsed for its
   full text, its time cell, its Plan/Optional tag, and every hyperlink.
   The first import (usa-2026.json) condensed the text and dropped all the
   links; this layer recovers both exactly as the source had them.
2. Curated (CURATED below): a short headline, a duration, an anchor time
   where the source pins one, cost, location, tips and booking status —
   written by hand from the source page and the family's notes doc
   (source-trip-notes.md), keyed by (day index, item index) in source order.
   These are judgement calls a parser can't make, so they live in code
   where a diff shows every change.

The output is a one-time import (building_an_app.md, "seeding is one-time
only"): `manage.py enrich_ustrip_items` reads it, fills items that are
still in their seeded state, and never touches anything the family has
edited. Re-running this script only matters if the source page changes.
"""

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source" / "daily-plan.html"
SEED = HERE / "usa-2026.json"
OUT = HERE / "usa-2026-items.json"

DAY_RE = re.compile(r'<details class="panel" id="(day[^"]+)"[^>]*>(.*?)</details>', re.S)
LI_RE = re.compile(r"<li>(.*?)</li>", re.S)
TIME_RE = re.compile(r'<span class="time">(.*?)</span>', re.S)
TAG_RE = re.compile(r'<span class="tag(?: warn)?">(Plan|Optional)</span>', re.S)
LINK_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
HHMM_RE = re.compile(r"^~?(\d{1,2}):(\d{2})")
PM_RE = re.compile(r"^(\d{1,2}):(\d{2})pm$")


def text_of(fragment):
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment)
    return re.sub(r"\s+", " ", fragment).strip()


def link_kind(url, label):
    if "wikipedia.org" in url:
        return "wikipedia"
    if "google.com/maps" in url or label.lower() == "map":
        return "map"
    return "official"


def fixed_start_from(time_cell):
    """"15:50" -> "15:50"; "~16:00" -> "16:00"; "17:15–19:15" -> "17:15";
    "1:00pm" -> "13:00"; "Evening"/"—"/"9:00–17:00 (opening hours)" -> None
    (opening-hour ranges are overridden in CURATED)."""
    cell = time_cell.strip()
    m = PM_RE.match(cell)
    if m:
        hour = int(m.group(1)) % 12 + 12
        return f"{hour:02d}:{m.group(2)}"
    m = HHMM_RE.match(cell)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    return None


def parse():
    src = SOURCE.read_text(encoding="utf-8")
    days = []
    for day_id, body in DAY_RE.findall(src):
        items = []
        for li in LI_RE.findall(body):
            time_cell = text_of(TIME_RE.search(li).group(1)) if TIME_RE.search(li) else ""
            tag_match = TAG_RE.search(li)
            tag = tag_match.group(1).lower() if tag_match else "rejected"
            desc_html = li.split("</span>", 1)[1] if "</span>" in li else li
            if tag_match:
                desc_html = desc_html.replace(tag_match.group(0), "", 1)
            links = [
                {"label": text_of(label), "url": html.unescape(url), "kind": link_kind(url, text_of(label))}
                for url, label in LINK_RE.findall(desc_html)
            ]
            items.append({
                "time_cell": time_cell,
                "tag": tag,
                "description": text_of(desc_html),
                "links": links,
                "fixed_start": fixed_start_from(time_cell),
            })
        days.append({"source_id": day_id, "items": items})
    return days


# (day index, item index) -> curated fields. Indexes follow source order,
# which is also the order seed_ustrip created the rows in (order = index).
# Every entry sets a title and a duration; the rest only where the source
# or the notes actually say something.
CURATED = {
    # ---- Day 1 — Arrival, NYC ---------------------------------------------
    (0, 0): {"title": "Land at Newark (EWR)", "duration": 60, "location": "Newark Liberty International Airport, NJ",
             "booking": "booked"},
    (0, 1): {"title": "Transfer to Manhattan", "duration": 60, "location": "EWR → Penn Station (W 34th St)",
             "cost": "NJ Transit ~$18/person (~$90 for 5); taxi/Uber $100–130",
             "tips": "NJ Transit is direct to Penn Station, 30–40 min. A taxi or Uber has no fixed price: the meter, "
                     "the NJ→NY surcharge, and tunnel tolls push it to $100–130, more if the Lincoln or Holland "
                     "tunnel is jammed."},
    (0, 2): {"title": "Check in: Delta Hotels Times Square", "duration": 30,
             "location": "Delta Hotels by Marriott New York Times Square", "booking": "booked"},
    (0, 3): {"title": "Times Square evening walk", "duration": 120, "location": "Times Square → Rockefeller Center",
             "tips": "7 min walk from the hotel. Do the loop — Broadway, Radio City, Rockefeller Center — and come "
                     "back through Times Square once the lights are on."},
    (0, 4): {"title": "Central Perk coffeehouse", "duration": 45, "location": "7th Ave & 47th St",
             "tips": "Friends-themed café with the orange couch, 8–10 min from the hotel. The Hershey's store in the "
                     "same complex hands out chocolate at the door and can print a photo of us on a wrapper."},
    (0, 5): {"title": "Dinner in Hell's Kitchen", "duration": 90, "location": "Hell's Kitchen"},
    (0, 6): {"title": "Sunset sail around Manhattan", "duration": 120, "booking": "to_book",
             "tips": "Classic Harbor Line or Manhattan by Sail — compare current times and prices."},
    # ---- Day 2 — Central Park, 5th Ave, Broadway -------------------------
    (1, 0): {"title": "Breakfast", "duration": 45},
    (1, 1): {"title": "Central Park walk", "duration": 180, "location": "Central Park, from Columbus Circle",
             "tips": "Columbus Circle → The Mall → Bethesda Terrace & Fountain → the lake → Bow Bridge → "
                     "Strawberry Fields (the John Lennon memorial)."},
    (1, 2): {"title": "Fifth Avenue", "duration": 150, "location": "Fifth Avenue, Midtown",
             "tips": "Apple Fifth Avenue, the LEGO Store, St. Patrick's Cathedral, Rockefeller Center."},
    (1, 3): {"title": "Nintendo New York", "duration": 30, "location": "10 Rockefeller Plaza"},
    (1, 4): {"title": "Top of the Rock", "duration": 75, "location": "30 Rockefeller Plaza", "cost": "~$42/person",
             "booking": "to_book",
             "tips": "Reserve a time slot ahead — cheaper online and it skips the ticket line. The view: Central "
                     "Park one way, the Empire State Building the other."},
    (1, 5): {"title": "Grand Central Terminal", "duration": 45, "location": "89 E 42nd St"},
    (1, 6): {"title": "Broadway musical", "duration": 180, "location": "Theater District", "booking": "to_book",
             "cost": "Rush / lottery ~$35–59 per person",
             "tips": "Same-day rush and lottery tickets exist for most shows — the family has had up to 50% off "
                     "this way. Lottery: sign up around 9:00, results by midday, one hour to buy. TodayTix rush "
                     "was $49; an Aladdin lottery win was $35 a seat."},
    # ---- Day 3 — Downtown & Brooklyn --------------------------------------
    (2, 0): {"title": "Packers @ Jets (NFL)", "duration": 210, "location": "MetLife Stadium, East Rutherford NJ",
             "booking": "to_book",
             "tips": "Instead of the Downtown/Brooklyn day — the Jets' home opener. This is the open decision for "
                     "the day."},
    (2, 1): {"title": "9/11 Memorial, Oculus & Wall Street", "duration": 150, "location": "Lower Manhattan",
             "tips": "Subway to Ground Zero; the Oculus is right there; short walk on to Wall Street and the "
                     "Charging Bull."},
    (2, 2): {"title": "Mercer Labs", "duration": 90, "location": "21 Dey St", "booking": "to_book",
             "tips": "Immersive art and technology museum, right in this area."},
    (2, 3): {"title": "Walk to Battery Park", "duration": 30, "location": "Battery Park"},
    (2, 4): {"title": "Statue of Liberty: ferry", "duration": 120,
             "cost": "Staten Island Ferry free; Statue City Cruises ~$26/person", "booking": "to_book",
             "tips": "Free Staten Island Ferry: every 15–20 min, ~25 min each way, stand on the right side heading "
                     "out for the statue. Or Statue City Cruises to Liberty Island — book ahead; $26 covers the "
                     "boat, the museum, the audio tour, and continuing to Ellis Island."},
    (2, 5): {"title": "Ferry to DUMBO & Time Out Market", "duration": 240, "location": "Pier 11 → DUMBO, Brooklyn",
             "cost": "NYC Ferry ~$4/person",
             "tips": "Lunch at Time Out Market; walk Brooklyn Bridge Park to the famous Manhattan Bridge photo "
                     "spot on Washington St."},
    (2, 6): {"title": "Walk the Brooklyn Bridge", "duration": 120, "location": "Brooklyn Bridge, DUMBO → Manhattan",
             "tips": "Sunset is ~19:00, so 17:15–19:15 gives daylight, golden hour, then the lights coming on. "
                     "~1.8 km, about 30 min at an easy pace; the DUMBO / Washington St entrance has a gentle ramp "
                     "up to the walkway."},
    (2, 7): {"title": "Dinner in Chinatown or SoHo", "duration": 90},
    (2, 8): {"title": "Meow Parlour cat café", "duration": 50, "location": "Lower East Side", "cost": "~$23",
             "booking": "to_book", "tips": "50 minutes; reserve ahead."},
    (2, 9): {"title": "Feast of San Gennaro", "duration": 90, "location": "Mulberry St, Little Italy",
             "tips": "Runs Sep 17–27, so it's on tonight — right next to Chinatown/SoHo. The family list says: "
                     "definitely doing this."},
    # ---- Day 4 — Hudson Yards, High Line, West Village -------------------
    (3, 0): {"title": "Hudson Yards & the Vessel", "duration": 75, "location": "Hudson Yards",
             "tips": "15 min walk from the hotel. If Top of the Rock was skipped, consider the Edge observation "
                     "deck here instead (~1.5 hrs)."},
    (3, 1): {"title": "City Climb at Edge", "duration": 120, "cost": "~$185/person (verify)", "booking": "to_book",
             "tips": "Extreme — verify current price and season."},
    (3, 2): {"title": "Intrepid Sea, Air & Space Museum", "duration": 150, "location": "Pier 86, W 46th St",
             "booking": "to_book",
             "tips": "High priority on the family list; a short walk up the riverfront from Hudson Yards."},
    (3, 3): {"title": "B&H Photo", "duration": 60, "location": "420 9th Ave",
             "tips": "Must-do per the list. Closed Saturdays — today (Monday) works."},
    (3, 4): {"title": "Walk the High Line", "duration": 90, "location": "High Line, from 30th St south",
             "tips": "~2 km south through gardens, art and views over the streets and the river — a park built "
                     "on the old elevated freight railway."},
    (3, 5): {"title": "Lunch: Chelsea Market or Pier 57", "duration": 75, "location": "Chelsea Market, 75 9th Ave",
             "tips": "Chelsea Market is an indoor food hall in the old Oreo factory; Pier 57 has rooftop seating "
                     "with the view."},
    (3, 6): {"title": "Little Island", "duration": 45, "location": "Pier 55, Hudson River Park",
             "tips": "A floating park on concrete 'tulips'; then a short walk through the cobblestones of the "
                     "Meatpacking District."},
    (3, 7): {"title": "Whitney Museum", "duration": 120, "location": "99 Gansevoort St",
             "tips": "Right at this end of the High Line; lower priority than MoMA."},
    (3, 8): {"title": "Greenwich Village", "duration": 150, "location": "Greenwich / West Village",
             "tips": "The flagship Harry Potter Store near the Flatiron Building, the Friends building on Bedford "
                     "St, Bleecker Street, Washington Square Park."},
    (3, 9): {"title": "National Museum of Mathematics (MoMath)", "duration": 90, "location": "225 5th Ave, Flatiron",
             "booking": "to_book"},
    (3, 10): {"title": "SoHo", "duration": 90, "location": "SoHo", "tips": "Cast-iron architecture, shopping."},
    (3, 11): {"title": "MoMA", "duration": 150, "location": "11 W 53rd St", "booking": "to_book",
              "tips": "Instead of part of this day. The main art option; the Whitney is lower priority."},
    (3, 12): {"title": "Jazz club: Village Vanguard or Smalls", "duration": 120, "location": "Greenwich Village",
              "booking": "to_book"},
    # ---- Day 5 — Finger Lakes ---------------------------------------------
    (4, 0): {"title": "Pick up the rental car", "duration": 45, "location": "Manhattan West Side, near W 40th St",
             "booking": "to_book",
             "tips": "See Trip essentials for the car. Ask for an E-ZPass / toll pass (cashless toll stretches in "
                     "NY and PA), unlimited mileage, one-way return at Newark, and cover for the night in Canada."},
    (4, 1): {"title": "Drive to the Finger Lakes", "duration": 255,
             "tips": "~400 km, 4–4.5 hrs. Stretch stop about 2 hrs in around Stroudsburg / Delaware Water Gap "
                     "(the Poconos) or Binghamton."},
    (4, 2): {"title": "Watkins Glen State Park — Gorge Trail", "duration": 120, "location": "Watkins Glen, NY",
             "cost": "Parking fee (the receipt is valid at other Finger Lakes parks)",
             "tips": "1.6 mi past 19 waterfalls, lots of steps — hiking shoes, picnic food. Keep the parking "
                     "receipt. The shuttle between parks only runs weekends after Sep 8."},
    (4, 3): {"title": "Seneca Lake scenic drive", "duration": 25, "location": "Route 14 along Seneca Lake"},
    # ---- Day 6 — Niagara Falls --------------------------------------------
    (5, 0): {"title": "Drive to Niagara Falls", "duration": 150},
    (5, 1): {"title": "Niagara Falls State Park (US side)", "duration": 120, "location": "Niagara Falls, NY",
             "tips": "Bring a change of socks and shoes — you will get completely soaked. Watch the phone in the "
                     "spray."},
    (5, 2): {"title": "Cave of the Winds", "duration": 60, "cost": "$23/person (poncho included)", "booking": "to_book",
             "tips": "Buy at the park; timed elevator entry. Get to the ticket window early, take the next free "
                     "slot, and walk the park (or do Maid of the Mist) in between."},
    (5, 3): {"title": "Maid of the Mist boat", "duration": 60, "cost": "$30.25/person", "booking": "to_book",
             "time_label": "Boats 9:00–17:00, every 15 min", "fixed_start": None,
             "tips": "No fixed time slot — board in order of arrival. Buy a few days ahead to skip the ticket line. "
                     "Blue poncho with a hood."},
    (5, 4): {"title": "Cross Rainbow Bridge, check in (Canada)", "duration": 45,
             "location": "Rainbow Bridge → Niagara Falls, ON"},
    (5, 5): {"title": "Niagara Parkway, Clifton Hill & fireworks", "duration": 150,
             "location": "Niagara Parkway / Clifton Hill, ON",
             "tips": "Panoramic view of all three falls; the falls are lit at night and there are fireworks. Bring "
                     "Canadian dollars — USD is accepted at a poor rate and change comes back in CAD."},
    # ---- Day 7 — Pennsylvania ---------------------------------------------
    (6, 0): {"title": "Drive toward Lancaster County", "duration": 240,
             "tips": "~6–6.5 hrs of driving today in total; leg-stretch stop after ~3.5 hrs."},
    (6, 1): {"title": "Leonard Harrison State Park — the PA Grand Canyon", "duration": 60, "location": "Wellsboro, PA",
             "cost": "Free entry and parking",
             "tips": "Overlook of Pine Creek Gorge a minute from the parking. Skip the steep Turkey Path; do the "
                     "short flat walk between viewpoints. The visitor center has small exhibits on the canyon."},
    (6, 2): {"title": "Lunch in Wellsboro", "duration": 60, "location": "Wellsboro, PA",
             "tips": "Gaslit Main Street, 19th-century small-town feel. Timeless Destination (Italian/American) "
                     "or Harland's Family Style Restaurant (quick, cheap)."},
    (6, 3): {"title": "Drive to Lancaster", "duration": 210, "tips": "Arrive ~18:30."},
    # ---- Day 8 — Amish Country → Washington DC ----------------------------
    (7, 0): {"title": "The Amish Farm and House tour", "duration": 180, "location": "2395 Covered Bridge Dr, Lancaster",
             "cost": "Classic ~$28.95/person; premium (1805 farmhouse) ~$36.95/person", "booking": "to_book",
             "tips": "Arrive 30 min before the bus. Tours leave 11:00 / 13:00 / 15:00; open 9–17. Some Amish "
                     "vendors are cash-only. Drinks and snacks are allowed."},
    (7, 1): {"title": "Amish Experience VIP Tour (dropped)", "duration": 210, "cost": "~$100 more per family",
             "tips": "Private, up to 14 people, ~3.5 hrs, workshops and working barns with the community — "
                     "dropped because it only runs at 17:00."},
    (7, 2): {"title": "Amish country drive: Bird-in-Hand, Intercourse, Strasburg", "duration": 90,
             "location": "Lancaster County back roads",
             "tips": "Farms without power lines, blacksmiths, huge barns, people working the fields with horses, "
                     "and black buggies alongside the cars."},
    (7, 3): {"title": "Tanger Outlets Lancaster", "duration": 120, "location": "311 Stanley K Tanger Blvd, Lancaster"},
    (7, 4): {"title": "Drive to Washington, DC", "duration": 180, "tips": "~120 mi, 2.5–3 hrs."},
    (7, 5): {"title": "Georgetown dinner & the monuments by night", "duration": 150, "location": "Georgetown, DC"},
    # ---- Day 9 — Washington DC & museums ----------------------------------
    (8, 0): {"title": "Capitol Hill", "duration": 60, "location": "US Capitol"},
    (8, 1): {"title": "National Museum of Natural History", "duration": 120,
             "location": "10th St & Constitution Ave NW", "cost": "Free",
             "tips": "No advance booking — it's security-line order; arrive early, before the big lines."},
    (8, 2): {"title": "Lunch", "duration": 60},
    (8, 3): {"title": "National Air and Space Museum", "duration": 135, "location": "600 Independence Ave SW",
             "cost": "Free (timed ticket)", "booking": "booked", "tips": "5 tickets already reserved."},
    (8, 4): {"title": "White House & the National Mall walk", "duration": 180, "location": "National Mall",
             "tips": "Family photo in front of the White House (20 min walk or 5 min taxi from the museums). Then "
                     "Washington Monument → WWII Memorial → Reflecting Pool → Vietnam & Korean War Memorials → "
                     "finish at the Lincoln Memorial lit up."},
    (8, 5): {"title": "Smithsonian museums: free entry", "duration": 0,
             "tips": "Reserve a free timed ticket in advance where required. Beyond Air & Space and Natural "
                     "History there's American History and the art galleries."},
    (8, 6): {"title": "International Spy Museum", "duration": 120, "location": "700 L'Enfant Plaza SW", "cost": "Paid",
             "booking": "to_book"},
    # ---- Day 10 — Philadelphia --------------------------------------------
    (9, 0): {"title": "Drive to Philadelphia", "duration": 165, "tips": "~2.5–3 hrs."},
    (9, 1): {"title": "Liberty Bell & Independence Hall", "duration": 120,
             "location": "Independence National Historical Park", "cost": "Free",
             "tips": "Liberty Bell, Independence Hall, Congress Hall / the President's House."},
    (9, 2): {"title": "Lunch: Reading Terminal Market", "duration": 60, "location": "51 N 12th St"},
    (9, 3): {"title": "Old City: Franklin Court & Elfreth's Alley", "duration": 90, "location": "Old City, Philadelphia"},
    (9, 4): {"title": "The Rocky Steps", "duration": 45, "location": "Philadelphia Museum of Art"},
    (9, 5): {"title": "Drive to Atlantic City, boardwalk & casino", "duration": 90,
             "tips": "~1.5 hrs → check in, the boardwalk, a casino."},
    # ---- Day 11 — Atlantic City -------------------------------------------
    (10, 0): {"title": "Beach, pool & Tanger Outlets Atlantic City", "duration": 480, "location": "Atlantic City, NJ",
              "tips": "No sales tax on clothes and shoes in NJ."},
    (10, 1): {"title": "A show", "duration": 150, "booking": "to_book"},
    # ---- Day 12–13 — New Jersey -------------------------------------------
    (11, 0): {"title": "Drive to New Jersey", "duration": 135, "tips": "~2–2.5 hrs."},
    (11, 1): {"title": "The Mills at Jersey Gardens", "duration": 180, "location": "651 Kapkowski Rd, Elizabeth NJ",
              "tips": "Huge indoor outlet mall near Newark."},
    (11, 2): {"title": "American Dream", "duration": 300, "location": "1 American Dream Way, East Rutherford NJ",
              "booking": "to_book", "tips": "Indoor water park, ice skating, Nickelodeon Universe rollercoasters."},
    (11, 3): {"title": "Six Flags Great Adventure", "duration": 360, "location": "Jackson, NJ", "booking": "to_book"},
    (11, 4): {"title": "Woodbury Common Premium Outlets", "duration": 240, "location": "Central Valley, NY"},
    (11, 5): {"title": "Quick trip into Manhattan", "duration": 240, "tips": "20–30 min by train or bus."},
    (11, 6): {"title": "Target / Kohl's in Secaucus; evening at Harmon Meadow", "duration": 180, "location": "Secaucus, NJ"},
    (11, 7): {"title": "Laundry & a melatonin run", "duration": 90},
    # ---- Day 14–15 — Flight home ------------------------------------------
    (12, 0): {"title": "Return the car: Newark Rental Car Center", "duration": 45,
              "location": "Newark Airport Rental Car Center (Station P3)",
              "tips": "Waze: 'Newark Airport Rental Car Center'. Fuel up 5–10 km before the airport on US-1/9 or "
                      "I-95 — airport and agency refuelling cost far more."},
    (12, 1): {"title": "Terminal A garage → AirTrain to the terminal", "duration": 30,
              "tips": "AirTrain (or the 5-min shuttle / 15-min walk) to Terminal A if departing from B or C."},
    (12, 2): {"title": "Depart Newark, UA84", "duration": 660, "booking": "booked"},
    (12, 3): {"title": "Land in Tel Aviv", "duration": 60, "booking": "booked"},
}


def build():
    days = parse()
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    seed_days = seed["days"]
    assert len(days) == len(seed_days), f"{len(days)} source days vs {len(seed_days)} seeded"

    out_days = []
    for day_index, (day, seed_day) in enumerate(zip(days, seed_days)):
        assert len(day["items"]) == len(seed_day["items"]), f"day {day_index}: item count differs from seed"
        out_items = []
        for item_index, (item, seed_item) in enumerate(zip(day["items"], seed_day["items"])):
            curated = CURATED[(day_index, item_index)]
            fixed_start = curated.get("fixed_start", item["fixed_start"])
            time_label = curated.get("time_label")
            if time_label is None:
                # Fuzzy cells ("Morning", "Evening", "Lunch", "Day") survive as a note; exact
                # ones became the anchor and would only repeat the computed time.
                time_label = "" if (fixed_start or item["time_cell"] in ("—", "")) else item["time_cell"]
            out_items.append({
                "seed_description": seed_item["desc"],
                "title": curated["title"],
                "description": item["description"],
                "tag": item["tag"],
                "time_label": time_label,
                "fixed_start": fixed_start,
                "duration_minutes": curated["duration"],
                "location": curated.get("location", ""),
                "cost": curated.get("cost", ""),
                "tips": curated.get("tips", ""),
                "booking": curated.get("booking", "not_needed"),
                "links": item["links"],
            })
        out_days.append({"day": seed_day["day"], "source_id": day["source_id"], "items": out_items})

    OUT.write_text(json.dumps({
        "_source": "docs/ustrip/trip-data/source/daily-plan.html (snapshot of "
                   "https://avisalmon.github.io/arhab/pages/daily-plan.html, 2026-09-14) + curated fields in "
                   "build_items_json.py",
        "_note": "One-time enrichment input for `manage.py enrich_ustrip_items`. `seed_description` is the text "
                 "usa-2026.json seeded, used as the guard: an item whose text no longer matches has been edited "
                 "by the family and is left alone.",
        "days": out_days,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(d["items"]) for d in out_days)
    links = sum(len(i["links"]) for d in out_days for i in d["items"])
    print(f"wrote {OUT.name}: {len(out_days)} days, {total} items, {links} links")


if __name__ == "__main__":
    build()
