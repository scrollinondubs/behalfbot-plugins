"""Write and read founder bundles. The spec is docs/bundle-format.md.

A bundle is built in memory as {path: bytes} and then written as a directory or
a .zip. Keeping one in-memory shape means both containers hold identical bytes,
and the round-trip test can compare bundles file by file.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from founder_ledger.interface import BUNDLE_TABLES, Ledger, LedgerError, NotFound, Row
from founder_ledger.migrate import migration_files

FORMAT = "founder-os-bundle"
FORMAT_VERSION = 1
SOURCES = ("vcl", "self-hosted")
MANIFEST = "manifest.json"
SUMS = "SHA256SUMS"

# Fixed forever: remapped ids are uuid5(REMAP_NAMESPACE, "<new founder_id>:<table>:<old id>").
# Changing it would make a second import of the same bundle duplicate every row.
REMAP_NAMESPACE = uuid.UUID("5b0d6f2e-8c1a-5f4e-9d3b-2a7c4e6f8b10")

ID_REFS = {
    "audits": "target_id",
    "labels": "target_id",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH = re.compile(
    r"^(ledger/[a-z_]+\.json|artifacts/stage-[0-9]/[a-z0-9-]+\.md|prfaq/v[0-9]+\.md|files/[0-9a-f]{64})$")
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class BundleError(LedgerError):
    """The bundle is malformed, tampered with, or from a newer format."""


# --- small helpers ------------------------------------------------------------

def _json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _schema_version() -> str:
    return migration_files()[-1][0]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "artifact"


def _front(fields: dict[str, Any]) -> str:
    # JSON scalars and lists are valid YAML, so the frontmatter parses as both.
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()]
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def _file_refs(artifact: Row) -> list[dict]:
    files = (artifact.get("meta") or {}).get("files") or []
    if not isinstance(files, list):
        raise BundleError(f"artifact {artifact['id']}: meta.files must be a list")
    for ref in files:
        if not isinstance(ref, dict) or not SHA256.match(str(ref.get("sha256", ""))):
            raise BundleError(f"artifact {artifact['id']}: every meta.files entry needs a lowercase sha256")
    return files


# --- export -------------------------------------------------------------------

SORT_KEYS = {
    "founders": lambda r: (r["founder_id"],),
    "stage_progress": lambda r: (r["stage"], r["id"]),
    "artifacts": lambda r: (r["kind"], r["version"]),
    "prfaq_versions": lambda r: (r["version"],),
}


def _default_sort(row: Row) -> tuple:
    return (row["created_at"], row["id"])


def _read_tables(ledger: Ledger, founder_id: str) -> dict[str, list[Row]]:
    founder = ledger.get_founder(founder_id)
    if founder is None:
        raise NotFound(f"no founder {founder_id!r}")
    tables = {
        "founders": [founder],
        "stage_progress": ledger.list_stage_progress(founder_id),
        "artifacts": ledger.list_artifacts(founder_id),
        "pains": ledger.list_pains(founder_id),
        "interviews": ledger.list_interviews(founder_id),
        "prfaq_versions": ledger.list_prfaq_versions(founder_id),
        "audits": ledger.list_audits(founder_id),
        "gate_decisions": ledger.list_gate_decisions(founder_id),
        "labels": ledger.list_labels(founder_id),
    }
    for table, rows in tables.items():
        rows.sort(key=SORT_KEYS.get(table, _default_sort))
    return tables


def build_bundle(
    ledger: Ledger, founder_id: str, *, source: str,
    files_dir: str | pathlib.Path | None = None, exported_at: str | None = None,
) -> dict[str, bytes]:
    """The bundle as {path: bytes}. export_bundle writes it out."""
    if source not in SOURCES:
        raise BundleError(f"source must be one of {', '.join(SOURCES)}, got {source!r}")
    tables = _read_tables(ledger, founder_id)
    out: dict[str, bytes] = {}

    for table in BUNDLE_TABLES:
        out[f"ledger/{table}.json"] = _json(tables[table])

    used: set[str] = set()
    for art in tables["artifacts"]:
        refs = _file_refs(art)
        name = f"artifacts/stage-{art['stage']}/{_slug(art['kind'])}-v{art['version']}.md"
        if name in used:
            name = name[:-3] + f"-{art['id'][:8]}.md"
        used.add(name)
        front = _front({
            "id": art["id"], "kind": art["kind"], "version": art["version"], "stage": art["stage"],
            "title": art["title"], "created_at": art["created_at"],
            "files": [f"files/{r['sha256']}" for r in refs],
        })
        out[name] = (front + art["body"].rstrip("\n") + "\n").encode("utf-8")
        for ref in refs:
            if files_dir is None:
                raise BundleError(f"artifact {art['id']} has attached files; pass files_dir to export them")
            blob = pathlib.Path(files_dir) / ref["sha256"]
            if not blob.is_file():
                raise BundleError(f"artifact {art['id']}: attached file {blob} is missing")
            data = blob.read_bytes()
            if _sha(data) != ref["sha256"]:
                raise BundleError(f"attached file {blob} does not match its sha256")
            out[f"files/{ref['sha256']}"] = data

    for pr in tables["prfaq_versions"]:
        front = _front({
            "id": pr["id"], "version": pr["version"], "stage": pr["stage"],
            "created_at": pr["created_at"], "assumptions": pr["assumptions"],
        })
        out[f"prfaq/v{pr['version']}.md"] = (front + pr["body"].rstrip("\n") + "\n").encode("utf-8")

    sums = "".join(f"{_sha(out[p])}  {p}\n" for p in sorted(out)).encode("utf-8")
    out[SUMS] = sums
    out[MANIFEST] = _json({
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "source": source,
        "founder_id": founder_id,
        "exported_at": exported_at or _now(),
        "schema_version": _schema_version(),
        "counts": {t: len(tables[t]) for t in BUNDLE_TABLES},
        "checksums": {"file": SUMS, "sha256": _sha(sums)},
    })
    return out


def write_bundle(files: dict[str, bytes], dest: str | pathlib.Path) -> pathlib.Path:
    dest = pathlib.Path(dest)
    if dest.suffix == ".zip":
        if dest.exists():
            raise BundleError(f"{dest} already exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(files):
                info = zipfile.ZipInfo(path, date_time=ZIP_DATE)
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, files[path])
        return dest
    if dest.exists() and any(dest.iterdir()):
        raise BundleError(f"{dest} exists and is not empty")
    for path, data in files.items():
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return dest


def export_bundle(
    ledger: Ledger, founder_id: str, dest: str | pathlib.Path, *, source: str = "self-hosted",
    files_dir: str | pathlib.Path | None = None,
) -> dict:
    """Write founder_id's bundle to dest (a new directory, or a path ending .zip).
    Returns the manifest."""
    files = build_bundle(ledger, founder_id, source=source, files_dir=files_dir)
    write_bundle(files, dest)
    return json.loads(files[MANIFEST])


# --- import -------------------------------------------------------------------

def load_files(src: str | pathlib.Path) -> dict[str, bytes]:
    src = pathlib.Path(src)
    if src.is_file() and zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            return {i.filename: zf.read(i) for i in zf.infolist() if not i.is_dir()}
    if src.is_dir():
        return {p.relative_to(src).as_posix(): p.read_bytes() for p in src.rglob("*") if p.is_file()}
    raise BundleError(f"{src} is not a bundle directory or .zip")


def read_bundle(src: str | pathlib.Path) -> tuple[dict, dict[str, list[Row]], dict[str, bytes]]:
    """Verify a bundle and return (manifest, tables, files). Raises BundleError
    on a newer format or schema, a checksum mismatch, or a missing or extra file."""
    files = load_files(src)
    if MANIFEST not in files:
        raise BundleError("no manifest.json - not a founder bundle")
    try:
        manifest = json.loads(files[MANIFEST])
    except ValueError as exc:
        raise BundleError(f"manifest.json is not JSON: {exc}") from exc

    if manifest.get("format") != FORMAT:
        raise BundleError(f"manifest format is {manifest.get('format')!r}, not {FORMAT!r}")
    version = manifest.get("format_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise BundleError(f"format_version must be a positive integer, got {version!r}")
    if version > FORMAT_VERSION:
        raise BundleError(
            f"bundle format_version {version} is newer than this plugin reads ({FORMAT_VERSION}). "
            "Update the founder-os plugin, then import again.")
    if manifest.get("source") not in SOURCES:
        raise BundleError(f"manifest source must be one of {', '.join(SOURCES)}")
    schema = str(manifest.get("schema_version", ""))
    if schema > _schema_version():
        raise BundleError(
            f"bundle ledger schema {schema} is newer than this install's ({_schema_version()}). "
            "Update the founder-os plugin, then import again.")

    sums = files.get(SUMS)
    if sums is None or _sha(sums) != (manifest.get("checksums") or {}).get("sha256"):
        raise BundleError("SHA256SUMS is missing or does not match the manifest")
    listed: dict[str, str] = {}
    for line in sums.decode("utf-8").splitlines():
        digest, _, path = line.partition("  ")
        if not SHA256.match(digest) or not path:
            raise BundleError(f"malformed SHA256SUMS line: {line!r}")
        listed[path] = digest
    present = set(files) - {MANIFEST, SUMS}
    if present != set(listed):
        extra = sorted(present - set(listed))
        missing = sorted(set(listed) - present)
        raise BundleError(f"bundle files do not match SHA256SUMS (extra: {extra}, missing: {missing})")
    for path, digest in listed.items():
        if not SAFE_PATH.match(path):
            raise BundleError(f"unexpected path in bundle: {path!r}")
        if _sha(files[path]) != digest:
            raise BundleError(f"checksum mismatch: {path}")
        if path.startswith("files/") and path != f"files/{digest}":
            raise BundleError(f"{path} is not named after its sha256")

    tables: dict[str, list[Row]] = {}
    for table in BUNDLE_TABLES:
        path = f"ledger/{table}.json"
        if path not in files:
            raise BundleError(f"missing {path}")
        rows = json.loads(files[path])
        if not isinstance(rows, list):
            raise BundleError(f"{path} must hold a JSON list")
        tables[table] = rows
    founders = tables["founders"]
    if len(founders) != 1 or founders[0].get("founder_id") != manifest.get("founder_id"):
        raise BundleError("ledger/founders.json must hold exactly the manifest's founder")
    for art in tables["artifacts"]:
        for ref in _file_refs(art):
            if f"files/{ref['sha256']}" not in files:
                raise BundleError(f"artifact {art['id']} references files/{ref['sha256']}, not in the bundle")
    return manifest, tables, files


def remap_founder(tables: dict[str, list[Row]], new_founder_id: str) -> dict[str, list[Row]]:
    """The same rows under new_founder_id, with every row id and every reference
    rewritten deterministically, so re-importing under the same id is a no-op."""
    def new(table: str, old: str) -> str:
        return str(uuid.uuid5(REMAP_NAMESPACE, f"{new_founder_id}:{table}:{old}"))

    out: dict[str, list[Row]] = {}
    for table, rows in tables.items():
        out[table] = []
        for row in rows:
            row = dict(row, founder_id=new_founder_id)
            if table != "founders":
                row["id"] = new(table, row["id"])
            if table in ID_REFS:
                row["target_id"] = new(row["target_table"], row["target_id"])
            if table == "gate_decisions":
                row["evidence"] = [{"table": e["table"], "id": new(e["table"], e["id"])} for e in row["evidence"]]
            out[table].append(row)
    return out


def import_bundle(
    ledger: Ledger, src: str | pathlib.Path, *, as_founder: str | None = None,
    replace: bool = False, files_dir: str | pathlib.Path | None = None,
) -> dict:
    """Verify and load a bundle. Idempotent: a second import of the same bundle
    changes nothing. Returns {"founder_id", "manifest", "counts", "files"}."""
    manifest, tables, files = read_bundle(src)
    founder_id = manifest["founder_id"]
    if as_founder and as_founder != founder_id:
        tables = remap_founder(tables, as_founder)
        founder_id = as_founder

    blobs = {p: d for p, d in files.items() if p.startswith("files/")}
    if blobs and files_dir is None:
        raise BundleError("the bundle carries attached files; pass files_dir to import them")

    counts = ledger.import_founder_rows(founder_id, tables, replace=replace)

    copied = 0
    for path, data in sorted(blobs.items()):
        target = pathlib.Path(files_dir) / path.split("/", 1)[1]
        if target.is_file() and _sha(target.read_bytes()) == target.name:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        tmp.write_bytes(data)
        shutil.move(tmp, target)
        copied += 1
    return {"founder_id": founder_id, "manifest": manifest, "counts": counts, "files": copied}
