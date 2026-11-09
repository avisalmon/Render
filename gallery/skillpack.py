"""Reading a skill upload safely, and packing it for both platforms
(REQ-G.50, G.55).

A skill arrives as a SKILL.md or a zip of its folder. Nothing in it is ever
run: the zip is read entry by entry in memory, with its size, its count and
every path checked before a byte is decompressed, so a zip bomb, a path out of
the folder, a link, or an archive inside the archive is refused, not opened.

Claude Code and GitHub Copilot read the same SKILL.md format (a header with
`name` and `description`, then instructions), and differ in where the folder
lives: `.claude/skills/<name>/` and `.github/skills/<name>/`. So a package is
the same files under each prefix. Anything that belongs to one platform only
is adapted by the skill chat (SPR-G.6), which says what it changed.
"""

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

MAX_TOTAL = 1024 * 1024          # bytes, all files together, after unpacking
MAX_FILES = 60
MAX_UPLOAD = 2 * 1024 * 1024     # bytes, the file as sent
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ARCHIVES = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".whl")
PLATFORM_PREFIXES = {(".claude", "skills"): "claude", (".github", "skills"): "copilot"}
CLAUDE_ONLY_FIELDS = ("allowed-tools", "model", "disable-model-invocation", "user-invocable", "context", "agent", "hooks")


class Refused(Exception):
    """The upload cannot be a skill. `key` names the reason for the strings
    table; `detail` carries the path or number the person needs to fix it."""

    def __init__(self, key, detail=""):
        super().__init__(f"{key}: {detail}")
        self.key, self.detail = key, detail


@dataclass
class Bundle:
    name: str
    description: str
    origin: str                                   # "claude" or "copilot"
    header: dict
    files: list = field(default_factory=list)     # [(path, bytes)], SKILL.md first

    @property
    def skill_md(self):
        return self.files[0][1].decode("utf-8")

    def text_of(self, path):
        for p, data in self.files:
            if p == path:
                return data.decode("utf-8")
        return None

    @property
    def total(self):
        return sum(len(d) for _, d in self.files)


# ---------------------------------------------------------------- the header


def read_header(text):
    """The `---` header of a SKILL.md as a dict of strings. A small reader on
    purpose (the site does not ship a YAML library): top-level `key: value`,
    quoted values, and `>` / `|` blocks; nested blocks are kept as raw text."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None
    header, key, block, raw = {}, None, None, []
    for line in lines[1:end]:
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top and not line[:1].isspace():
            if key and (block or raw):
                header[key] = _join(raw, block)
            key, value = top.group(1).lower(), top.group(2).strip()
            raw, block = [], None
            if value in (">", "|", ">-", "|-", ">+", "|+"):
                block = value[0]
            elif value:
                header[key] = _unquote(value)
                key = None
        elif key is not None:
            raw.append(line.strip() if block else line)
    if key and (block or raw):
        header[key] = _join(raw, block)
    return header


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _join(raw, block):
    raw = [r for r in raw]
    while raw and not raw[-1].strip():
        raw.pop()
    return ("\n" if block == "|" else " ").join(raw).strip() if block else "\n".join(raw)


# ---------------------------------------------------------------- reading an upload


def _clean_path(name):
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or "\\" in name:
        raise Refused("skill.bad_path", name)
    parts = PurePosixPath(name).parts
    if any(p in ("..", "") for p in parts):
        raise Refused("skill.bad_path", name)
    return "/".join(parts)


def _strip_root(paths):
    """The folder the files sit in: `my-skill/`, `.claude/skills/my-skill/`,
    `.github/skills/my-skill/`, or nothing. Returns (prefix, origin hint)."""
    md = [p for p in paths if PurePosixPath(p).name.lower() == "skill.md"]
    if not md:
        raise Refused("skill.no_skill_md")
    depth = min(p.count("/") for p in md)
    shallowest = [p for p in md if p.count("/") == depth]
    if len(shallowest) > 1:
        raise Refused("skill.many_skills")
    top = shallowest[0]
    parts = PurePosixPath(top).parts[:-1]
    hint = PLATFORM_PREFIXES.get(tuple(parts[:2])) if len(parts) >= 2 else None
    prefix = "/".join(parts)
    return (prefix + "/" if prefix else ""), top, hint


def read_upload(filename, data):
    """A Bundle from the file a person sent, or Refused. Nothing is written
    anywhere and nothing is run."""
    if len(data) > MAX_UPLOAD:
        raise Refused("skill.too_big", f"{len(data) // 1024}KB")
    lower = (filename or "").lower()
    if lower.endswith(".zip") or data[:4] == b"PK\x03\x04":
        entries, hint, md_path = _read_zip(data)
    elif lower.endswith(".md"):
        entries, hint, md_path = [("SKILL.md", data)], None, "SKILL.md"
    else:
        raise Refused("skill.kind")
    files = []
    for path, content in entries:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise Refused("skill.not_text", path) from None
        files.append((path, content))
    files.sort(key=lambda f: (f[0] != md_path, f[0]))
    if files[0][0] != "SKILL.md":
        files[0] = ("SKILL.md", files[0][1])
    text = files[0][1].decode("utf-8")
    header = read_header(text)
    if header is None:
        raise Refused("skill.no_header")
    name = (header.get("name") or "").strip()
    description = (header.get("description") or "").strip()
    if not name or not description:
        raise Refused("skill.no_name_description")
    if not NAME.match(name) or len(name) > 64:
        raise Refused("skill.bad_name", name[:80])
    if len(description) > 1024:
        raise Refused("skill.long_description")
    # Where it came from: the folder it sat in says so; otherwise Claude Code,
    # whose format both platforms read.
    origin = hint or "claude"
    return Bundle(name=name, description=description, origin=origin, header=header, files=files)


def _read_zip(data):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Refused("skill.bad_zip") from None
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if len(infos) > MAX_FILES:
        raise Refused("skill.too_many", str(len(infos)))
    # Sizes are checked from the directory before anything is decompressed.
    if sum(i.file_size for i in infos) > MAX_TOTAL:
        raise Refused("skill.too_big", f"{sum(i.file_size for i in infos) // 1024}KB")
    paths = []
    for info in infos:
        path = _clean_path(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise Refused("skill.link", path)
        if path.lower().endswith(ARCHIVES):
            raise Refused("skill.archive_inside", path)
        if info.flag_bits & 0x1:
            raise Refused("skill.encrypted", path)
        paths.append(path)
    if len(set(p.lower() for p in paths)) != len(paths):
        raise Refused("skill.bad_path", "duplicate names")
    prefix, md_path, hint = _strip_root(paths)
    entries = []
    for info, path in zip(infos, paths):
        if not path.startswith(prefix):
            continue  # files outside the skill's folder are not part of it
        if PurePosixPath(path).name in ("__MACOSX", ".DS_Store") or path.startswith("__MACOSX/"):
            continue
        with zf.open(info) as fh:
            content = fh.read(MAX_TOTAL + 1)
        if len(content) != info.file_size:
            raise Refused("skill.bad_zip")
        entries.append((path[len(prefix):], content))
    return entries, hint, md_path[len(prefix):]


# ---------------------------------------------------------------- packing


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def package(bundle, platform):
    """A zip ready to unpack at a repo's root: the same files under
    `.claude/skills/<name>/` or `.github/skills/<name>/`."""
    root = {"claude": ".claude", "copilot": ".github"}[platform]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in bundle.files:
            zf.writestr(f"{root}/skills/{bundle.name}/{path}", data)
    return out.getvalue()


def original(bundle):
    """What was checked, as one zip, kept with the version for the record."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in bundle.files:
            zf.writestr(f"{bundle.name}/{path}", data)
    return out.getvalue()
