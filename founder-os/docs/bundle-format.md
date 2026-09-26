# Founder bundle format, version 1

A founder bundle holds one founder's ledger: every row they own, plus readable
copies of their artifacts and the original files attached to them. VCL exports
it from the student dashboard, and `founder-os import` loads it into a
self-hosted Behalf.bot. Bundles also move between self-hosted installs, and
back to VCL.

This file is the contract. `founder_bundle/bundle.py` is the reference
implementation. VCL's TypeScript exporter has to produce the same bytes for the
same rows. `tests/test_bundle_sqlite.py` checks that an export, an import into a
fresh database and a second export give identical bundles. The only permitted
difference is the manifest's `exported_at`.

## Container

A bundle is a directory, or a `.zip` of that directory with the same paths. Both
forms hold identical bytes. In the zip, entries are sorted by path, deflated,
and dated 1980-01-01 00:00:00 with mode 0644, so the same bundle always zips to
the same bytes.

```
manifest.json
SHA256SUMS
ledger/founders.json
ledger/stage_progress.json
ledger/artifacts.json
ledger/pains.json
ledger/interviews.json
ledger/prfaq_versions.json
ledger/audits.json
ledger/gate_decisions.json
ledger/labels.json
artifacts/stage-<n>/<kind-slug>-v<version>.md
prfaq/v<version>.md
files/<sha256>
```

No other paths are allowed. An import refuses a bundle with an unexpected path
or a file that is not in `SHA256SUMS`.

## manifest.json

```json
{
  "checksums": {"file": "SHA256SUMS", "sha256": "<hex sha256 of SHA256SUMS>"},
  "counts": {"founders": 1, "stage_progress": 2, "artifacts": 3, "...": 0},
  "exported_at": "2026-09-26T10:00:00.000000Z",
  "format": "founder-os-bundle",
  "format_version": 1,
  "founder_id": "<the founder's id>",
  "schema_version": "001",
  "source": "self-hosted"
}
```

| Field | Meaning |
|---|---|
| `format` | Always `founder-os-bundle`. |
| `format_version` | Integer. It goes up when a reader of the old version could not read the new one correctly. An importer refuses a version newer than it knows, with a message to update the plugin, and it writes nothing. |
| `source` | `vcl` or `self-hosted`: which kind of install wrote it. |
| `founder_id` | The founder the bundle holds. It must equal the one row in `ledger/founders.json`. |
| `exported_at` | ISO-8601 UTC. The only field allowed to differ between two exports of the same rows. |
| `schema_version` | The newest ledger migration the exporter's schema has (`schema/migrations/NNN_*.sql`). An importer on an older schema refuses the bundle. |
| `counts` | Rows per table, for humans and a quick sanity check. |
| `checksums` | Where the file checksums are, and the sha256 of that file. |

## JSON encoding

Every JSON file in the bundle is UTF-8, keys sorted, two-space indent, non-ASCII
characters written as-is rather than `\u` escaped, and one trailing newline.
Python's `json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"`
produces it. A TypeScript exporter has to match it byte for byte.

## ledger/*.json

One file per ledger table, each a JSON list of rows. Every file is present, so a
table with no rows is `[]`. Rows use the column names from
`schema/migrations/`, all columns present, shaped the way the storage interface
returns them:

- JSON columns (`context`, `meta`, `tags`, `assumptions`, `evidence`,
  `model_label`, `corrected_label`) are JSON values, not strings holding JSON.
- `earlyvangelist` and `sean_signoff` are `true` / `false`.
- ids, timestamps and every other value are exactly as stored. An import never
  generates an id or a timestamp.

Rows are sorted so the order does not depend on the database engine:

| Table | Order |
|---|---|
| `founders` | the one row |
| `stage_progress` | `stage`, then `id` |
| `artifacts` | `kind`, then `version` |
| `prfaq_versions` | `version` |
| every other table | `created_at`, then `id` |

Only the founder's own rows are exported. The one cross-founder read in the
interface, `export_corrected_labels`, is never used here.

## Artifacts as markdown

Each artifact is also written as `artifacts/stage-<stage>/<kind-slug>-v<version>.md`,
and each PR/FAQ version as `prfaq/v<version>.md`, so a founder can read their
work without a database. `kind-slug` is the kind lowercased with every run of
characters outside `a-z0-9` turned into `-`. If two kinds slug to the same name,
the later one in the sort order gets `-<first 8 chars of its id>` appended.

The file is a frontmatter block, a blank line, then the body with trailing
newlines trimmed to one. Frontmatter values are JSON, which is also valid YAML:

```markdown
---
id: "3f0c..."
kind: "why"
version: 1
stage: 0
title: "Why bikes"
created_at: "2026-09-26T10:00:00.000000Z"
files: ["files/9a4e..."]
---

# Why
...
```

PR/FAQ files carry `id`, `version`, `stage`, `created_at` and `assumptions`.

These files are a readable copy. The rows in `ledger/` are canonical, and an
import reads only the rows. The markdown is still checksummed, so a bundle with
edited markdown is refused rather than loaded with a copy that disagrees with
its rows.

## Attached files

The ledger stores text. An original file, such as a sprint recording or a PDF of
a signed pilot, is attached to an artifact through its `meta`:

```json
{"files": [{"sha256": "<lowercase hex>", "name": "pilot.pdf", "media_type": "application/pdf"}]}
```

Only `sha256` is required. The bytes live in a content-addressed store named by
`FOUNDER_OS_FILES_DIR`, one file per blob, named by its sha256. In the bundle,
each blob is `files/<sha256>`. An export fails if a referenced file is missing
or its bytes do not match its hash. An import copies each blob into the local
store and skips blobs already there. Nothing in the plugin writes attachments
yet. This convention is what the first skill that stores one has to follow.

## SHA256SUMS

One line per file except `manifest.json` and `SHA256SUMS` itself, sorted by
path, in the format `sha256sum` writes and checks:

```
<64 hex>  ledger/artifacts.json
```

`cd bundle && sha256sum -c SHA256SUMS` verifies a directory bundle by hand. The
manifest records the sha256 of `SHA256SUMS`, which chains every file to the
manifest. On import, a missing file, an extra file, a mismatched hash, or a
`files/<name>` whose bytes do not hash to `<name>` refuses the whole bundle.
The checksums catch corruption and accidental edits. They are not a signature:
anyone can edit a bundle and recompute them.

## Import

`founder-os import <bundle>` verifies everything above, then calls the storage
interface's `import_founder_rows` once. That call is one transaction:

1. Rows load in dependency order: `founders`, `stage_progress`, `artifacts`,
   `pains`, `interviews`, `prfaq_versions`, `audits`, `gate_decisions`, `labels`.
2. A row whose id is already present with identical content is skipped. That
   makes import idempotent: importing the same bundle twice changes nothing.
3. A row whose id is present with different content, or that belongs to another
   founder, is a conflict. The import is refused, nothing is written, and the
   error lists every conflicting row. This happens when the founder kept working
   on this install after an earlier import. `--replace` deletes this founder's
   local rows and loads the bundle. Any local work that is not in the bundle is
   lost.
4. After loading, every audit target, label target and gate evidence ref has to
   point at a row this founder owns, or the import is refused.
5. The schema's `CHECK` constraints still apply: no gate decision without
   evidence, and no pass from stage 3 onward without Sean's sign-off.

## How ids are remapped

By default nothing is remapped. ids are UUIDs made by the application
(`schema/README.md`), so rows keep their ids and a bundle round-trips exactly.

`--as-founder <id>` imports the bundle under a different `founder_id`. Use it
when an install's founder id convention differs from VCL's, or to load a copy
beside the original. Every row id is then replaced with

```
uuid5(5b0d6f2e-8c1a-5f4e-9d3b-2a7c4e6f8b10, "<new founder_id>:<table>:<old id>")
```

and the references are rewritten with the same function: `audits.target_id`,
`labels.target_id` (using their `target_table`), and each `{table, id}` in
`gate_decisions.evidence`. `founder_id` is set to the new value everywhere. The
mapping is deterministic, so importing the same bundle under the same new id
twice is still a no-op. The namespace UUID is fixed forever: changing it would
duplicate every row on re-import.

## Progress webhook

After a VCL student moves to a self-hosted install, the instructor loses sight
of them. The progress webhook reports stage progress back. It is optional and
off by default.

**Turning it on.** The operator sets both `progress_webhook_url` and
`progress_webhook_secret` in the plugin config, exported as
`FOUNDER_OS_PROGRESS_WEBHOOK_URL` and `FOUNDER_OS_PROGRESS_WEBHOOK_SECRET`. The
instructor issues both, one pair per student. With no URL, nothing is ever sent.
A URL without a secret is an error, never an unsigned send. The URL has to be
`https` (plain `http` is allowed only to localhost, for testing).

`founder-os progress --founder-id <id>` sends the current state, and
`--print` shows the exact payload without sending. When stage skills ship, they
call it after `mark_gate_pending` and `record_gate_decision`.

**What is sent: this and nothing else.**

```json
{"gate_status":"gate_pending","stage":3,"updated_at":"2026-09-26T10:00:00.000000Z"}
```

| Field | Value |
|---|---|
| `stage` | The founder's current stage, 0-9. |
| `gate_status` | That stage's `stage_progress.status`: `in_progress`, `gate_pending` or `passed`. A failed gate shows up as the stage it routed back to, `in_progress`. |
| `updated_at` | That stage row's `updated_at`. |

**The privacy boundary.** The payload has no founder id, name, cohort, artifact,
quote, interview, audit, label, evidence or rationale. The sender refuses a
payload with any other key. The instructor learns which student it is only from
the per-student URL they issued. Everything the founder wrote stays on their
install. The instructor sees where a graduate is in the sequence and when that
last changed, and nothing about what is in their ledger. The receiver still sees
the request's source IP, as with any HTTP request.

**Signing.** Each request carries two headers:

```
X-FounderOS-Timestamp: <unix seconds when sent>
X-FounderOS-Signature: sha256=<hex HMAC-SHA256(secret, "<timestamp>." + raw body)>
```

The body is compact JSON, keys sorted, as sent. A receiver verifies it like this:

1. Read the raw request body before any JSON parsing. Parsing and re-serialising
   can change the bytes.
2. Reject the request if the timestamp is not an integer, or is more than 300
   seconds from the receiver's clock, either way. This stops a captured request
   from being replayed later.
3. Compute `"sha256=" + hex(HMAC-SHA256(secret, timestamp + "." + body))` with
   the secret for the student this URL belongs to.
4. Compare it to the header with a constant-time comparison
   (`hmac.compare_digest`, `crypto.timingSafeEqual`). Reject on mismatch.
5. Optionally, ignore a report whose `updated_at` is older than the last one
   stored for that student.

`founder_bundle.progress.verify(secret, timestamp, body, signature)` is the
reference receiver check. In TypeScript on VCL:

```ts
const ts = req.headers.get("x-founderos-timestamp") ?? "";
const sig = req.headers.get("x-founderos-signature") ?? "";
const body = await req.text();
if (!/^\d+$/.test(ts) || Math.abs(Date.now() / 1000 - Number(ts)) > 300) return reject();
const want = "sha256=" + createHmac("sha256", secret).update(`${ts}.${body}`).digest("hex");
if (want.length !== sig.length || !timingSafeEqual(Buffer.from(want), Buffer.from(sig))) return reject();
```

## Changing the format

Adding a table or column means a new migration and a new `schema_version`, and
older importers refuse the bundle with a clear message. Anything that changes
how an existing file is written or read (paths, encoding, the remap function)
bumps `format_version`, and this file is updated in the same PR.
