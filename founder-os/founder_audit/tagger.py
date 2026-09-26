"""Run a question set over one piece of text: route, chunk, ask, aggregate.

Questions are grouped by the checkpoint they route to. Each group is one Laya
call per chunk, so a set that splits across two checkpoints costs two calls on
short text.

Long text is split, never truncated. #603 found 590 of 2,057 posts longer than
the multilingual window and 1,587 longer than the English one, and Laya cuts
the tail off silently. The richest pain was in exactly those long posts. So
text is chunked on paragraph, then sentence, then word boundaries to fit the
checkpoint, every chunk is asked, and the answers are combined per question:

    max   a noul or score takes the chunk with the highest value. One chunk
          describing a pain makes the post a pain post.
    mean  a choice averages its option probabilities over the chunks.

Chunk sizes are in characters, set well under each window, because the plugin
has no tokenizer. If a chunk still reaches the window (usage.input_tokens per
question at the cap), the result says so in `truncated`.
"""
from __future__ import annotations

import re
from typing import Any

from .laya import CHECKPOINT_MAX_TOKENS, LayaClient
from .questions import QuestionSet, guess_lang

# State characters per chunk. English: 512 tokens less up to 192 for the question
# head leaves about 320; at a conservative 3 characters per token that is ~1,000.
# Multilingual: 1,024 less 192 leaves about 830; non-English text runs denser.
CHUNK_CHARS = {"english": 1000, "multilingual": 2400, "typed-decisions": 2400}

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        for sent in _SENTENCE_END.split(para):
            if len(sent) <= max_chars:
                pieces.append(sent)
                continue
            cur = ""
            for w in sent.split():
                while len(w) > max_chars:
                    if cur:
                        pieces.append(cur)
                        cur = ""
                    pieces.append(w[:max_chars])
                    w = w[max_chars:]
                if cur and len(cur) + 1 + len(w) > max_chars:
                    pieces.append(cur)
                    cur = w
                else:
                    cur = f"{cur} {w}".strip()
            if cur:
                pieces.append(cur)
    # Pack small pieces back together up to the budget, keeping order.
    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + 2 + len(piece) <= max_chars:
            chunks[-1] = chunks[-1] + "\n\n" + piece
        else:
            chunks.append(piece)
    return chunks


def _noul_p(answer: dict) -> float:
    return float(answer.get("noul", 0.0))


def _aggregate(qset: QuestionSet, qid: str, answers: list[dict]) -> dict[str, Any]:
    kind = qset.questions[qid]["type"]
    how = qset.aggregate(qid)
    out: dict[str, Any] = {"type": kind}
    if kind == "noul":
        ps = [_noul_p(a) for a in answers]
        if how == "max":
            i = max(range(len(ps)), key=ps.__getitem__)
            p, conf = ps[i], answers[i].get("answer_confidence", answers[i].get("confidence"))
            out["chunk"] = i
        else:
            p = sum(ps) / len(ps)
            conf = max(p, 1 - p)
        out.update(value=p >= qset.threshold(qid), p=round(p, 4), confidence=conf)
    elif kind == "score":
        scores = [float(a.get("score", 0.0)) for a in answers]
        if how == "max":
            i = max(range(len(scores)), key=scores.__getitem__)
            s, conf, probs = scores[i], answers[i].get("answer_confidence"), answers[i].get("probabilities")
            out["chunk"] = i
        else:
            s, conf, probs = sum(scores) / len(scores), None, None
        out.update(value=int(round(s)), score=round(s, 4), confidence=conf, probabilities=probs)
    else:
        if how == "max":
            i = max(range(len(answers)), key=lambda j: max((answers[j].get("probabilities") or {0: 0}).values()))
            probs = dict(answers[i].get("probabilities") or {})
            out["chunk"] = i
        else:
            probs = {}
            for a in answers:
                for k, v in (a.get("probabilities") or {}).items():
                    probs[k] = probs.get(k, 0.0) + float(v) / len(answers)
        if probs:
            choice = max(probs, key=probs.__getitem__)
        else:
            choice = answers[0].get("choice")
        out.update(value=choice, probabilities={k: round(v, 4) for k, v in probs.items()},
                   confidence=round(probs.get(choice, 0.0), 4) if probs else answers[0].get("confidence"))
    return out


class Tagger:
    def __init__(self, qset: QuestionSet, client: LayaClient) -> None:
        self.qset = qset
        self.client = client

    def tag(self, text: str, *, lang: str | None = None, only: list[str] | None = None,
            runtime: dict | None = None) -> dict[str, Any]:
        """Tag one text. Returns {"lang", "results": {qid: result}, "skipped": {qid: why}}.
        Raises LayaUnavailable if the server cannot answer; the auditors catch it."""
        lang = lang or guess_lang(text)
        results: dict[str, Any] = {}
        skipped: dict[str, str] = {}
        groups: dict[str, dict[str, dict]] = {}
        for qid in only if only is not None else list(self.qset.questions):
            wire = self.qset.wire_question(qid, runtime)
            if wire is None:
                skipped[qid] = f"needs runtime criteria '{self.qset.runtime_key(qid)}'"
                continue
            groups.setdefault(self.qset.checkpoint_for(qid, lang), {})[qid] = wire

        for checkpoint, questions in groups.items():
            chunks = chunk_text(text, CHUNK_CHARS[checkpoint]) or [""]
            per_chunk: list[dict] = []
            truncated = False
            for chunk in chunks:
                resp = self.client.systemone(chunk, questions, model=checkpoint)
                per_chunk.append(resp["answers"])
                tokens = (resp.get("usage") or {}).get("input_tokens")
                if isinstance(tokens, int) and tokens // len(questions) >= CHECKPOINT_MAX_TOKENS[checkpoint]:
                    truncated = True
                served = (resp.get("routing") or {}).get("model") or resp.get("model")
            for qid in questions:
                r = _aggregate(self.qset, qid, [a[qid] for a in per_chunk])
                r.update(checkpoint=served if served in CHECKPOINT_MAX_TOKENS else checkpoint,
                         trust=self.qset.trust_for(qid, checkpoint), chunks=len(chunks), truncated=truncated)
                # On long text, point at the chunk that carried the answer so
                # Claude can check the evidence instead of rereading everything.
                if len(chunks) > 1 and "chunk" in r:
                    r["excerpt"] = chunks[r["chunk"]][:400]
                results[qid] = r
        return {"lang": lang, "results": results, "skipped": skipped}
