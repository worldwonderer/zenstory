"""
Resolve explicit skill selections embedded in the user message prefix.

Current frontend behavior injects a skill trigger or skill name directly into
the message text instead of sending a structured selected-skill payload. This
module treats those leading tokens as an explicit per-message skill choice so
the backend can enforce the intended skill instructions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from models import PublicSkill, UserAddedSkill, UserSkill
from utils.logger import get_logger, log_with_context

logger = get_logger(__name__)

_DELIMITER_CHARS = " \t\r\n,，.。:：;；!！?？/\\|+-—()[]{}<>\"'“”‘’"
_MAX_PREFIX_SKILL_STRIPS = 8


@dataclass(frozen=True)
class ExplicitSkillSelection:
    """Resolved explicit skill selection for the current message."""

    skill_id: str
    name: str
    instructions: str
    source: str
    matched_text: str
    cleaned_message: str


@dataclass(frozen=True)
class _SkillCandidate:
    skill_id: str
    name: str
    instructions: str
    source: str
    names: tuple[str, ...]
    triggers: tuple[str, ...]


@dataclass(frozen=True)
class _PrefixMatch:
    candidate: _SkillCandidate
    matched_text: str
    matched_kind: str


def resolve_explicit_skill_selection(
    *,
    session: Session,
    user_id: str | None,
    message: str,
) -> ExplicitSkillSelection | None:
    """
    Resolve a skill explicitly selected via the message prefix.

    Only leading skill names / triggers are considered explicit. This avoids
    accidental activation from normal free-form text.
    """
    if not user_id:
        return None

    raw_message = str(message or "")
    normalized_message = raw_message.lstrip()
    if not normalized_message:
        return None

    candidates = _load_skill_candidates(session, user_id)
    if not candidates:
        return None

    initial_match = _match_prefix(normalized_message, candidates)
    if initial_match is None:
        return None

    cleaned_message = normalized_message
    strip_count = 0
    while strip_count < _MAX_PREFIX_SKILL_STRIPS:
        next_match = _match_prefix(cleaned_message, candidates)
        if next_match is None:
            break
        cleaned_message = _strip_matched_prefix(cleaned_message, next_match.matched_text)
        strip_count += 1

    selection = ExplicitSkillSelection(
        skill_id=initial_match.candidate.skill_id,
        name=initial_match.candidate.name,
        instructions=initial_match.candidate.instructions,
        source=initial_match.candidate.source,
        matched_text=initial_match.matched_text,
        cleaned_message=cleaned_message,
    )

    log_with_context(
        logger,
        20,
        "Resolved explicit skill selection from message prefix",
        user_id=user_id,
        skill_id=selection.skill_id,
        skill_name=selection.name,
        skill_source=selection.source,
        matched_text=selection.matched_text,
        cleaned_message_empty=not bool(selection.cleaned_message),
        stripped_prefix_count=strip_count,
    )
    return selection


def _load_skill_candidates(session: Session, user_id: str) -> list[_SkillCandidate]:
    candidates: list[_SkillCandidate] = []

    user_skills = session.exec(
        select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.is_active,
        )
    ).all()
    for skill in user_skills:
        candidates.append(
            _SkillCandidate(
                skill_id=skill.id,
                name=skill.name,
                instructions=skill.instructions,
                source="user",
                names=_unique_non_empty((skill.name,)),
                triggers=_parse_json_array(skill.triggers),
            )
        )

    added_results = session.exec(
        select(UserAddedSkill, PublicSkill)
        .join(PublicSkill, UserAddedSkill.public_skill_id == PublicSkill.id)
        .where(
            UserAddedSkill.user_id == user_id,
            UserAddedSkill.is_active,
            PublicSkill.status == "approved",
        )
    ).all()
    for added, public in added_results:
        display_name = (added.custom_name or public.name or "").strip()
        candidates.append(
            _SkillCandidate(
                skill_id=public.id,
                name=display_name,
                instructions=public.instructions,
                source="added",
                names=_unique_non_empty((display_name, public.name)),
                triggers=_parse_json_array(public.tags),
            )
        )

    return candidates


def _match_prefix(message: str, candidates: list[_SkillCandidate]) -> _PrefixMatch | None:
    ranked_matches: list[tuple[tuple[int, int, int], _PrefixMatch]] = []

    for candidate in candidates:
        for signal in candidate.names:
            if _has_explicit_prefix(message, signal):
                ranked_matches.append(
                    (
                        (len(signal), 2, _source_priority(candidate.source)),
                        _PrefixMatch(
                            candidate=candidate,
                            matched_text=signal,
                            matched_kind="name",
                        ),
                    )
                )
        for signal in candidate.triggers:
            if _has_explicit_prefix(message, signal):
                ranked_matches.append(
                    (
                        (len(signal), 1, _source_priority(candidate.source)),
                        _PrefixMatch(
                            candidate=candidate,
                            matched_text=signal,
                            matched_kind="trigger",
                        ),
                    )
                )

    if not ranked_matches:
        return None

    ranked_matches.sort(key=lambda item: item[0], reverse=True)
    best_score, best_match = ranked_matches[0]

    conflicting_matches = [
        match
        for score, match in ranked_matches[1:]
        if score == best_score
    ]
    if conflicting_matches:
        log_with_context(
            logger,
            30,
            "Ambiguous explicit skill prefix; skipping forced selection",
            matched_text=best_match.matched_text,
            message_preview=message[:80],
            conflict_count=1 + len(conflicting_matches),
            candidate_ids=[best_match.candidate.skill_id, *[match.candidate.skill_id for match in conflicting_matches]],
        )
        return None

    return best_match


def _has_explicit_prefix(message: str, signal: str) -> bool:
    normalized_signal = str(signal or "").strip()
    if not normalized_signal:
        return False
    if not message.startswith(normalized_signal):
        return False
    if len(message) == len(normalized_signal):
        return True
    next_char = message[len(normalized_signal)]
    return next_char in _DELIMITER_CHARS or next_char.isspace()


def _strip_matched_prefix(message: str, matched_text: str) -> str:
    if not message.startswith(matched_text):
        return message
    remainder = message[len(matched_text):]
    return remainder.lstrip(_DELIMITER_CHARS)


def _parse_json_array(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    return _unique_non_empty(str(item) for item in parsed if item is not None)


def _unique_non_empty(values) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            continue
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(value)
    return tuple(deduped)


def _source_priority(source: str) -> int:
    if source == "user":
        return 2
    if source == "added":
        return 1
    return 0
