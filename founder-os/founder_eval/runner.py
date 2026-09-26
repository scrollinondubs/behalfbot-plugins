"""Run arms against fixture sets, score them, and write the results file.

The model call is a function argument, so CI can run the whole pipeline with a
mocked model and the live run can call `claude -p`. Nothing here decides what
counts as a win except decide(), and it is the same function for both.
"""
from __future__ import annotations

import concurrent.futures as futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import time
from typing import Callable

from .sets import TASKS, load_set, render, score
from .subjects import Subject, system_prompt

WIN_MARGIN = 0.05
BASELINE = "baseline"

# (system prompt, user prompt) -> {"text": str, "model": str, "cost_usd": float}
ModelFn = Callable[[str, str], dict]


def user_prompt(set_name: str, item: dict) -> str:
    return f"{TASKS[set_name]}\n\n--- item ---\n{render(set_name, item)}\n--- end ---\n\nReply with only the JSON object."


def parse_json(text: str) -> dict | None:
    """The first JSON object in the reply, fenced or bare."""
    if not text:
        return None
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[i:])
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def decide(delta: float, margin: float = WIN_MARGIN) -> str:
    if delta >= margin:
        return "win"
    if delta <= -margin:
        return "loss"
    return "null"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run(subject_list: list[Subject], model: ModelFn, *, repeats: int = 1, jobs: int = 4,
        laya_url: str | None = None, sets: list[str] | None = None,
        log: Callable[[str], None] = lambda s: None) -> dict:
    """Every subject on its fixture set, plus plain Claude on every set used.
    Returns {"calls": [...]} with one row per (arm, item, repeat)."""
    wanted = sorted({s.fixture_set for s in subject_list if sets is None or s.fixture_set in sets})
    arms: list[tuple[str, Subject | None, str]] = [(BASELINE, None, fs) for fs in wanted]
    arms += [(s.id, s, s.fixture_set) for s in subject_list if s.fixture_set in wanted]
    fixtures = {fs: load_set(fs) for fs in wanted}

    tasks = []
    for arm_id, subject, fs in arms:
        for item in fixtures[fs]["items"]:
            system = system_prompt(subject, fs, item, laya_url)
            user = user_prompt(fs, item)
            for r in range(repeats):
                tasks.append((arm_id, fs, item, r, system, user))

    def one(task):
        arm_id, fs, item, r, system, user = task
        t0 = time.monotonic()
        try:
            reply = model(system, user)
            error = None
        except Exception as e:  # a failed call scores 0 and is recorded, never dropped
            reply, error = {"text": "", "model": None, "cost_usd": 0.0}, f"{type(e).__name__}: {e}"
        pred = parse_json(reply.get("text", ""))
        item_score, parts = score(fs, pred, item)
        return {
            "arm": arm_id, "fixture_set": fs, "item": item["id"], "repeat": r,
            "score": round(item_score, 4), "parts": {k: round(v, 4) for k, v in parts.items()},
            "parsed": pred is not None, "answer": pred, "raw": reply.get("text", ""), "error": error,
            "model": reply.get("model"), "cost_usd": reply.get("cost_usd", 0.0),
            "seconds": round(time.monotonic() - t0, 2),
            "system_sha": _sha(system), "user_sha": _sha(user),
        }

    calls = []
    with futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for n, row in enumerate(pool.map(one, tasks), start=1):
            calls.append(row)
            log(f"[{n}/{len(tasks)}] {row['arm']} {row['item']} r{row['repeat']}: {row['score']}")
    return {"calls": calls}


def summarise(calls: list[dict], subject_list: list[Subject], *, run_id: str, mode: str, model: str,
              repeats: int, laya: str | None, notes: str = "") -> dict:
    def mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    # A call that errored (the CLI or API failed, no answer came back) is not a
    # model answer. It is counted and published, and left out of the scores on
    # both sides. An answer that came back but does not parse is a model answer
    # and scores 0.
    by_arm: dict[tuple[str, str], list[dict]] = {}
    errors: dict[tuple[str, str], int] = {}
    for c in calls:
        key = (c["arm"], c["fixture_set"])
        if c.get("error"):
            errors[key] = errors.get(key, 0) + 1
        else:
            by_arm.setdefault(key, []).append(c)

    baselines = {}
    for (arm, fs), rows in sorted(by_arm.items()):
        if arm == BASELINE:
            baselines[fs] = {"score": mean([r["score"] for r in rows]), "n_calls": len(rows),
                             "parse_failures": sum(1 for r in rows if not r["parsed"]),
                             "errors": errors.get((arm, fs), 0)}

    subjects_out = {}
    for s in subject_list:
        key = (s.id, s.fixture_set)
        rows = by_arm.get(key, [])
        if key not in by_arm and key not in errors:
            continue
        if not rows or s.fixture_set not in baselines:
            subjects_out[s.id] = {"kind": s.kind, "fixture_set": s.fixture_set, "stage": s.stage, "laya": s.laya,
                                  "errors": errors.get(key, 0), "verdict": "incomplete"}
            continue
        items = sorted({r["item"] for r in rows})
        base_rows = [r for r in by_arm[(BASELINE, s.fixture_set)] if r["item"] in items]
        subject_score = mean([r["score"] for r in rows])
        base_score = mean([r["score"] for r in base_rows])
        delta = round(subject_score - base_score, 4)
        per_repeat = []
        for r in range(repeats):
            a = [x["score"] for x in rows if x["repeat"] == r]
            b = [x["score"] for x in base_rows if x["repeat"] == r and x["item"] in {y["item"] for y in rows if y["repeat"] == r}]
            per_repeat.append(round(mean(a) - mean(b), 4) if a and b else None)
        wins = sum(1 for i in items
                   if mean([r["score"] for r in rows if r["item"] == i])
                   > mean([r["score"] for r in base_rows if r["item"] == i]))
        losses = sum(1 for i in items
                     if mean([r["score"] for r in rows if r["item"] == i])
                     < mean([r["score"] for r in base_rows if r["item"] == i]))
        parts: dict[str, list[float]] = {}
        base_parts: dict[str, list[float]] = {}
        for r in rows:
            for k, v in r["parts"].items():
                parts.setdefault(k, []).append(v)
        for r in base_rows:
            for k, v in r["parts"].items():
                base_parts.setdefault(k, []).append(v)
        subjects_out[s.id] = {
            "kind": s.kind, "fixture_set": s.fixture_set, "stage": s.stage, "laya": s.laya,
            "n_items": len(items), "repeats": repeats, "n_calls": len(rows),
            "score": subject_score, "baseline": base_score, "delta": delta,
            "delta_per_repeat": per_repeat, "items_better": wins, "items_worse": losses,
            "parts": {k: mean(v) for k, v in sorted(parts.items())},
            "baseline_parts": {k: mean(v) for k, v in sorted(base_parts.items())},
            "parse_failures": sum(1 for r in rows if not r["parsed"]),
            "errors": errors.get(key, 0),
            "files": list(s.files),
            "verdict": decide(delta),
        }
    return {
        "run_id": run_id, "mode": mode, "date": dt.date.today().isoformat(), "model": model,
        "laya": laya, "repeats": repeats,
        "decision_rule": {"win_margin": WIN_MARGIN,
                          "rule": "win if mean score minus plain Claude's is at least the margin, "
                                  "loss if it is at most minus the margin, null otherwise"},
        "notes": notes,
        "baselines": baselines,
        "subjects": subjects_out,
        "cost_usd": round(sum(c.get("cost_usd") or 0.0 for c in calls), 4),
        "calls": len(calls),
    }


def markdown(results: dict) -> str:
    lines = [f"# Eval results: {results['run_id']}", "",
             f"Mode: {results['mode']}. Model: {results['model']}. Laya: {results['laya'] or 'not used'}. "
             f"Repeats: {results['repeats']}. Date: {results['date']}. Calls: {results['calls']}, "
             f"cost ${results['cost_usd']}.", "",
             "Every subject is scored against plain Claude on the same fixture set, the same task text and "
             f"the same items. Win: at least +{results['decision_rule']['win_margin']} over plain Claude. "
             "Loss: at most minus that. Anything between is a null result, published the same as a win. "
             "A call that errored (no answer came back) is counted in Calls and left out of the scores on "
             "both sides; plain Claude is compared on the same items the subject answered.", "",
             "| Subject | Kind | Stage | Set | Items | Calls | Score | Plain Claude | Delta | Per repeat | Items better/worse | Verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid, s in sorted(results["subjects"].items(), key=lambda kv: (kv[1]["stage"], kv[0])):
        if s["verdict"] == "incomplete":
            lines.append(f"| `{sid}` | {s['kind']} | {s['stage']} | {s['fixture_set']} | - | 0 | - | - | - | - | - "
                         f"| **incomplete** ({s['errors']} errored calls) |")
            continue
        calls = f"{s['n_calls']}" + (f" ({s['errors']} errored)" if s.get("errors") else "")
        per = ", ".join("n/a" if d is None else f"{d:+.3f}" for d in s["delta_per_repeat"])
        lines.append(f"| `{sid}` | {s['kind']} | {s['stage']} | {s['fixture_set']} | {s['n_items']} | {calls} | "
                     f"{s['score']:.3f} | {s['baseline']:.3f} | {s['delta']:+.3f} | {per} | "
                     f"{s['items_better']}/{s['items_worse']} | **{s['verdict']}** |")
    lines += ["", "## Where the points came from", ""]
    for sid, s in sorted(results["subjects"].items(), key=lambda kv: (kv[1]["stage"], kv[0])):
        if s["verdict"] == "incomplete":
            continue
        comps = ", ".join(f"{k} {v:.2f} vs {s['baseline_parts'].get(k, 0):.2f}" for k, v in s["parts"].items())
        lines.append(f"- `{sid}`: {comps}.")
    if results.get("notes"):
        lines += ["", "## Notes", "", results["notes"]]
    return "\n".join(lines) + "\n"


def claude_cli(model: str, workdir: pathlib.Path, timeout: int = 300) -> ModelFn:
    """A ModelFn that calls `claude -p` with no tools, no MCP servers and a
    replaced system prompt, from an empty working directory."""
    workdir.mkdir(parents=True, exist_ok=True)

    def call(system: str, user: str) -> dict:
        prompt_file = workdir / f"system-{_sha(system)}.txt"
        if not prompt_file.exists():
            prompt_file.write_text(system, encoding="utf-8")
        last = None
        for attempt in range(3):
            proc = subprocess.run(
                ["claude", "-p", "--model", model, "--system-prompt-file", str(prompt_file),
                 "--tools", "", "--strict-mcp-config", "--no-session-persistence", "--output-format", "json"],
                input=user, capture_output=True, text=True, cwd=workdir, timeout=timeout)
            if proc.returncode == 0:
                try:
                    data = json.loads(proc.stdout)
                    return {"text": data.get("result", ""),
                            "model": ",".join(sorted(data.get("modelUsage", {}))) or model,
                            "cost_usd": data.get("total_cost_usd", 0.0)}
                except ValueError as e:
                    last = f"unparseable CLI output: {e}"
            else:
                last = f"exit {proc.returncode}: {proc.stderr.strip()[:300]}"
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(last)

    return call
