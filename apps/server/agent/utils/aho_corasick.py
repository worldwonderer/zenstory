"""
Deterministic Aho-Corasick term matching helpers.

Provides:
- Multi-pattern substring matching in linear time
- Longest-match filtering
- Ambiguity disabling for overlapping ties
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MatchSpan:
    """A matched term span in text."""

    term: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return max(0, self.end - self.start)


class AhoCorasickMatcher:
    """A small, dependency-free Aho-Corasick matcher."""

    def __init__(self, terms: Iterable[str]):
        cleaned = self._dedupe_terms(terms)
        self._terms = tuple(cleaned)
        self._transitions: list[dict[str, int]] = [{}]
        self._fail: list[int] = [0]
        self._outputs: list[list[str]] = [[]]
        self._build_automaton()

    @property
    def is_empty(self) -> bool:
        return not self._terms

    def find_matches(self, text: str) -> list[MatchSpan]:
        """Find all raw matches in text."""
        if self.is_empty or not text:
            return []

        state = 0
        matches: list[MatchSpan] = []
        for index, ch in enumerate(text):
            while state and ch not in self._transitions[state]:
                state = self._fail[state]
            state = self._transitions[state].get(ch, 0)

            outputs = self._outputs[state]
            if not outputs:
                continue

            end = index + 1
            for term in outputs:
                start = end - len(term)
                if start < 0:
                    continue
                matches.append(MatchSpan(term=term, start=start, end=end))

        return matches

    @staticmethod
    def _dedupe_terms(terms: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for term in terms:
            normalized = str(term or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
        return out

    def _build_automaton(self) -> None:
        if self.is_empty:
            return

        for term in self._terms:
            state = 0
            for ch in term:
                next_state = self._transitions[state].get(ch)
                if next_state is None:
                    next_state = len(self._transitions)
                    self._transitions.append({})
                    self._fail.append(0)
                    self._outputs.append([])
                    self._transitions[state][ch] = next_state
                state = next_state
            self._outputs[state].append(term)

        queue: deque[int] = deque()
        for next_state in self._transitions[0].values():
            queue.append(next_state)
            self._fail[next_state] = 0

        while queue:
            state = queue.popleft()
            for ch, next_state in self._transitions[state].items():
                queue.append(next_state)

                fallback = self._fail[state]
                while fallback and ch not in self._transitions[fallback]:
                    fallback = self._fail[fallback]
                fail_state = self._transitions[fallback].get(ch, 0)
                self._fail[next_state] = fail_state

                inherited_outputs = self._outputs[fail_state]
                if inherited_outputs:
                    self._outputs[next_state].extend(inherited_outputs)


def select_longest_non_ambiguous_matches(matches: list[MatchSpan]) -> list[MatchSpan]:
    """
    Keep one longest match per overlap group; drop ties as ambiguous.

    Rules:
    - Overlapping matches form a group.
    - Keep the unique longest span in a group.
    - If multiple spans share max length in a group, discard the group.
    """
    if not matches:
        return []

    deduped = {(m.term, m.start, m.end): m for m in matches}
    ordered = sorted(
        deduped.values(),
        key=lambda m: (m.start, m.end, m.term),
    )
    if not ordered:
        return []

    groups: list[list[MatchSpan]] = []
    current_group: list[MatchSpan] = [ordered[0]]
    current_end = ordered[0].end

    for match in ordered[1:]:
        if match.start < current_end:
            current_group.append(match)
            current_end = max(current_end, match.end)
            continue

        groups.append(current_group)
        current_group = [match]
        current_end = match.end

    groups.append(current_group)

    selected: list[MatchSpan] = []
    for group in groups:
        max_length = max(match.length for match in group)
        winners = [match for match in group if match.length == max_length]
        if len(winners) != 1:
            continue
        selected.append(winners[0])

    return sorted(selected, key=lambda m: (m.start, m.end, m.term))
