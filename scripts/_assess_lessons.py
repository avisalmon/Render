"""Assess all 15 lessons for completeness."""
import sqlite3, json
from pathlib import Path

db = sqlite3.connect('data/db.sqlite3')
rows = db.execute('''
    SELECT v.lesson_order, v.bunny_video_id, v.is_free_preview
    FROM app_video v
    JOIN app_course c ON v.course_id = c.id
    WHERE c.slug = 'micropython-thonny'
    ORDER BY v.lesson_order
''').fetchall()
db.close()

bunny = {r[0]: (r[1], r[2]) for r in rows}
base = Path('data/course_materials/micropython-thonny')
print(f'DB has {len(bunny)} Video records\n')

for i in range(1, 16):
    f = base / f'lesson_{i:02d}.json'
    d = json.loads(f.read_text(encoding='utf-8'))
    a = d.get('analysis') or {}

    has_analysis  = bool(a.get('title_en'))
    has_code      = bool(d.get('github_file'))
    t_len         = len(d.get('transcript_he', ''))
    bunny_id, free = bunny.get(i, (None, False))
    title_en      = a.get('title_en', '(missing)')[:42]

    flags = []
    if not has_analysis:  flags.append('NO_ANALYSIS')
    if t_len < 200:       flags.append('THIN_TRANSCRIPT(%dc)' % t_len)
    if not bunny_id:      flags.append('NO_BUNNY_ID')

    ready = 'READY' if (has_analysis and bunny_id and t_len > 100) else 'NEEDS_WORK'
    code_str = (d.get('github_file') or 'none')[:28]
    flag_str = ', '.join(flags) if flags else 'OK'
    print('L%02d [%9s] %-43s code=%-28s  %s' % (i, ready, title_en, code_str, flag_str))
