"""Plain lyrics <-> SynthV-style note lyrics: one token per note, '+' holds the previous word, '-' is a note with no word.

Guideline only (the format is loosely specified): words land on the note whose onset follows them, further notes inside
the word's time span become '+', notes outside any word become '-'.
"""
from __future__ import annotations

import difflib
import re

Word = tuple[float, float, str]  # start, end, text
Note = tuple[float, float]  # start, end

TOL = 0.1  # seconds of slack between a word's timing and a note's onset
ARPA = set("aa ae ah ao aw ax axr ay eh er ey ih ix iy ow oy uh uw ux b ch d dh dx el em en f g hh jh k l m n ng nx p q r "
           "s sh t th v w y z zh".split())


def to_synthv(words: list[Word], notes: list[Note]) -> tuple[str, int]:
    """(lyrics, number of words that found no note). Unplaced words are appended in order so no text is lost."""
    pending = sorted(words)
    tokens: list[str] = []
    held_until = float("-inf")  # end of the last word placed on a note
    for start, _end in sorted(notes):
        due = []
        while pending and pending[0][0] <= start + TOL:
            due.append(pending.pop(0))
        if due:
            tokens.append(" ".join(w[2].strip() for w in due))
            held_until = due[-1][1]
        elif start <= held_until + TOL:
            tokens.append("+")
        elif not tokens or tokens[-1] != "-":  # a run of word-less notes is one break
            tokens.append("-")
    unplaced = len(pending)
    tokens += [w[2].strip() for w in pending]
    return " ".join(tokens), unplaced


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower())


def _plain(token: str) -> bool:
    return token not in ("+", "-") and not token.startswith(".") and token.lower() not in ARPA


def from_synthv(synthv: str, original: str) -> tuple[str, int]:
    """(clean lyrics, number of synthv words the original did not confirm).

    Markers and phoneme runs are dropped and the original text, with its own line breaks, is the result; the count tells
    how many remaining words (respellings, edits) had to be taken from the original instead.
    """
    mine = [_norm(t) for t in synthv.split() if _plain(t)]
    mine = [m for m in mine if m]
    theirs = [_norm(w) for w in original.split()]
    theirs = [t for t in theirs if t]
    matcher = difflib.SequenceMatcher(None, mine, theirs, autojunk=False)
    unconfirmed = sum(i2 - i1 for tag, i1, i2, _j1, _j2 in matcher.get_opcodes() if tag != "equal")
    return "\n".join(line.rstrip() for line in original.strip().splitlines()) + "\n", unconfirmed
