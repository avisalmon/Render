"""Where the institutions are (backlog B.2): a city's region and the point
the map pins it at. Used once by the import to seed `Institution.region`,
`lat` and `lng`; after that the rows are the truth and an edit in the app
(a campus moved, a better point) is never overwritten.
"""

REGIONS = [
    ("north", "הצפון"),
    ("haifa", "חיפה"),
    ("center", "המרכז"),
    ("tel_aviv", "תל אביב"),
    ("jerusalem", "ירושלים"),
    ("south", "הדרום"),
    ("judea_samaria", "יהודה ושומרון"),
]
REGION_LABELS = dict(REGIONS)

# city -> (region, lat, lng); the main campus, to the nearest few hundred metres
CITIES = {
    "אלקנה": ("judea_samaria", 32.108, 35.038),
    "אריאל": ("judea_samaria", 32.105, 35.185),
    "אשקלון": ("south", 31.669, 34.571),
    "באר שבע": ("south", 31.262, 34.801),
    "חולון": ("tel_aviv", 32.015, 34.773),
    "חיפה": ("haifa", 32.777, 35.022),
    "טבעון": ("north", 32.719, 35.118),
    "ירושלים": ("jerusalem", 31.776, 35.198),
    "כנרת": ("north", 32.709, 35.568),
    "כפר סבא": ("center", 32.191, 34.893),
    "כרמיאל": ("north", 32.908, 35.292),
    "עמק חפר": ("center", 32.342, 34.912),
    "עמק יזרעאל": ("north", 32.653, 35.282),
    "צפת": ("north", 32.966, 35.496),
    "ראשון לציון": ("center", 31.969, 34.773),
    "רמת גן": ("tel_aviv", 32.070, 34.843),
    "רעננה": ("center", 32.176, 34.895),
    "שער הנגב": ("south", 31.510, 34.594),
    "תל אביב": ("tel_aviv", 32.113, 34.805),
    "תל אביב-יפו": ("tel_aviv", 32.113, 34.805),
    "תל חי": ("north", 33.237, 35.578),
}


# institutions the reference left without a city: slug -> (city, region, lat, lng)
BY_SLUG = {
    "jamd": ("ירושלים", "jerusalem", 31.776, 35.198),
    "hadassah": ("ירושלים", "jerusalem", 31.783, 35.221),
    "achva": ("באר טוביה", "south", 31.731, 34.761),
    "western-galilee": ("עכו", "north", 32.921, 35.089),
}


def place(city, slug=""):
    """(city, region, lat, lng) for a city the table knows (or a slug the
    reference left without a city), else None."""
    if slug in BY_SLUG:
        return BY_SLUG[slug]
    hit = CITIES.get((city or "").strip())
    return ((city or "").strip(),) + hit if hit else None
