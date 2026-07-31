#!/usr/bin/env python3
"""parse-youtube.py - extract transcript + metadata from a YouTube URL.

Usage:
    python3 parse-youtube.py <url_or_video_id> [--lang en] [--format json|markdown|both]

Output (JSON):
    {
      "video_id": "...",
      "title": "...",
      "channel": "...",
      "duration_seconds": 1234,
      "language": "en",
      "description": "...",
      "chapters": [{"title": "...", "start": 0}],
      "transcript": [{"start": 0.0, "duration": 2.5, "text": "..."}],
      "full_text": "...",
      "markdown": "..."   // only when --format includes markdown
    }

Config comes from the plugin manifest's configSchema, surfaced as env vars:
    PARSE_YOUTUBE_DEFAULT_LANG            preferred caption language (default: en)
    PARSE_YOUTUBE_FALLBACK_LANGS          comma-separated fallbacks (default: en)
    PARSE_YOUTUBE_METADATA                'false' to skip the yt-dlp call
    PARSE_YOUTUBE_METADATA_TIMEOUT        seconds before yt-dlp is abandoned (default: 30)
    PARSE_YOUTUBE_DESCRIPTION_MAX_CHARS   description truncation (default: 1000)

Every one of those has a working default, so the script runs standalone with no
environment at all. Nothing here is install-specific.
"""

import argparse
import json
import os
import re
import subprocess
import sys


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"warning: {name}={raw!r} is not an integer, using {default}", file=sys.stderr)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=)|youtu\.be/)([^\"&?/\s]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def format_timestamp(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fetch_with_transcript_api(video_id: str, languages: list[str]) -> dict:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    # Preferred languages first, then any auto-generated track in those
    # languages, then whatever the video has. The last step matters more than it
    # looks: a talk with only Korean captions is still worth returning.
    transcript = None
    errors = []
    for lang in languages:
        try:
            transcript = transcript_list.find_transcript([lang])
            break
        except Exception as e:  # noqa: BLE001 - the library raises several distinct types here
            errors.append(str(e))

    if transcript is None:
        try:
            transcript = transcript_list.find_generated_transcript(languages)
        except Exception:  # noqa: BLE001
            available = list(transcript_list)
            if available:
                transcript = available[0]
            else:
                raise RuntimeError(f"No transcript available. Errors: {'; '.join(errors)}")

    fetched = transcript.fetch()
    # 1.x FetchedTranscript is an iterable of FetchedTranscriptSnippet objects;
    # the dict branch keeps the parsing working against a 0.x install.
    segments = []
    for s in fetched:
        start = s.start if hasattr(s, "start") else s["start"]
        duration = s.duration if hasattr(s, "duration") else s["duration"]
        text = s.text if hasattr(s, "text") else s["text"]
        segments.append({
            "start": start,
            "duration": duration,
            "text": text.replace("\n", " ").strip(),
        })
    full_text = " ".join(s["text"] for s in segments)

    return {
        "segments": segments,
        "full_text": full_text,
        "language": transcript.language_code,
    }


def fetch_metadata_ytdlp(video_id: str, timeout: int, description_max_chars: int) -> dict:
    """Fetch title, channel, description, duration, chapters via yt-dlp.

    Returns {} on any failure. This is deliberately best-effort: metadata is a
    nicety, the transcript is the product, and a yt-dlp that broke against a
    YouTube player change should not take the whole run down with it.
    """
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode != 0:
            return {}
        data = json.loads(result.stdout)
        chapters = []
        for ch in (data.get("chapters") or []):
            chapters.append({"title": ch.get("title", ""), "start": int(ch.get("start_time", 0))})
        return {
            "title": data.get("title"),
            "channel": data.get("uploader") or data.get("channel"),
            "duration_seconds": data.get("duration"),
            "description": (data.get("description") or "")[:description_max_chars],
            "chapters": chapters,
        }
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}


def build_markdown(result: dict) -> str:
    lines = []
    lines.append(f"# {result.get('title') or 'Untitled'}")
    if result.get("channel"):
        lines.append(f"**Channel:** {result['channel']}")
    if result.get("duration_seconds"):
        lines.append(f"**Duration:** {format_timestamp(result['duration_seconds'])}")
    lines.append("")

    if result.get("chapters"):
        lines.append("## Chapters")
        for ch in result["chapters"]:
            ts = format_timestamp(ch["start"])
            lines.append(f"- [{ts}] {ch['title']}")
        lines.append("")

    if result.get("description"):
        lines.append("## Description")
        lines.append(result["description"])
        lines.append("")

    lines.append("## Transcript")
    for seg in result.get("transcript", []):
        ts = format_timestamp(seg["start"])
        lines.append(f"**[{ts}]** {seg['text']}")

    return "\n".join(lines)


def resolve_languages(cli_lang: str | None) -> list[str]:
    """Build the ordered language preference list.

    CLI wins, then the configured default, then the configured fallback chain.
    Duplicates are dropped while preserving order.
    """
    ordered: list[str] = []
    if cli_lang:
        ordered.extend(part.strip() for part in cli_lang.split(",") if part.strip())
    else:
        default_lang = os.environ.get("PARSE_YOUTUBE_DEFAULT_LANG", "en").strip()
        if default_lang:
            ordered.append(default_lang)

    fallbacks = os.environ.get("PARSE_YOUTUBE_FALLBACK_LANGS", "en")
    ordered.extend(part.strip() for part in fallbacks.split(",") if part.strip())

    seen: set[str] = set()
    result: list[str] = []
    for lang in ordered:
        if lang not in seen:
            seen.add(lang)
            result.append(lang)
    return result or ["en"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract YouTube transcript + metadata")
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    parser.add_argument("--lang", default=None,
                        help="Preferred language code(s), comma-separated. Overrides the configured default.")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="json",
                        help="Output format (default: json)")
    parser.add_argument("--no-metadata", action="store_true",
                        help="Skip the yt-dlp metadata fetch for a faster transcript-only run.")
    args = parser.parse_args()

    video_id = extract_video_id(args.url)
    if not video_id:
        print(json.dumps({"error": f"Could not extract video ID from: {args.url}"}), file=sys.stderr)
        return 1

    languages = resolve_languages(args.lang)

    try:
        transcript_data = fetch_with_transcript_api(video_id, languages)
    except Exception as e:  # noqa: BLE001 - surfaced verbatim to the caller
        print(json.dumps({"error": f"Transcript fetch failed: {e}", "video_id": video_id}), file=sys.stderr)
        return 1

    want_metadata = _env_bool("PARSE_YOUTUBE_METADATA", True) and not args.no_metadata
    meta = {}
    if want_metadata:
        meta = fetch_metadata_ytdlp(
            video_id,
            timeout=_env_int("PARSE_YOUTUBE_METADATA_TIMEOUT", 30),
            description_max_chars=_env_int("PARSE_YOUTUBE_DESCRIPTION_MAX_CHARS", 1000),
        )

    result = {
        "video_id": video_id,
        "title": meta.get("title"),
        "channel": meta.get("channel"),
        "duration_seconds": meta.get("duration_seconds"),
        "language": transcript_data["language"],
        "description": meta.get("description", ""),
        "chapters": meta.get("chapters", []),
        "transcript": transcript_data["segments"],
        "full_text": transcript_data["full_text"],
    }

    if args.format in ("markdown", "both"):
        result["markdown"] = build_markdown(result)

    if args.format == "markdown":
        print(result["markdown"])
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
