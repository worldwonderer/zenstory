"""
Text matching utilities for fuzzy and approximate text matching.

This module provides robust text matching functions that handle:
- Punctuation and whitespace variations
- Case differences
- Approximate/fuzzy matching for slight word errors

These utilities are used by the file editing operations to reliably locate
text anchors in content even when there are minor differences.
"""

import unicodedata
from difflib import SequenceMatcher


def normalize_for_fuzzy_match(
    s: str,
    *,
    ignore_punct_whitespace: bool = True,
    casefold: bool = True,
) -> tuple[str, list[int]]:
    """Normalize text for fuzzy matching.

    This function preprocesses text to enable robust matching by:
    - Normalizing Unicode characters (NFKC)
    - Optionally casefolding for case-insensitive matching
    - Optionally removing whitespace and punctuation

    Args:
        s: Input string to normalize
        ignore_punct_whitespace: If True, remove whitespace and punctuation
        casefold: If True, apply casefolding for case-insensitive matching

    Returns:
        A tuple of:
            - normalized: The normalized string
            - index_map: Mapping from each normalized char position to original index
    """
    normalized_chars: list[str] = []
    index_map: list[int] = []

    for idx, ch in enumerate(s):
        chunk = unicodedata.normalize("NFKC", ch)
        if casefold:
            chunk = chunk.casefold()

        for out_ch in chunk:
            if ignore_punct_whitespace:
                # Remove whitespace and punctuation for robust matching
                if out_ch.isspace():
                    continue
                if unicodedata.category(out_ch).startswith("P"):
                    continue

            normalized_chars.append(out_ch)
            index_map.append(idx)

    return "".join(normalized_chars), index_map


def find_fuzzy_spans(
    content: str,
    pattern: str,
    *,
    ignore_punct_whitespace: bool = True,
    casefold: bool = True,
    min_normalized_len: int = 6,
    max_matches: int = 20,
) -> list[tuple[int, int]]:
    """Find match spans in original content, ignoring punctuation/whitespace.

    This function finds all occurrences of a pattern in content, using
    fuzzy matching that ignores punctuation and whitespace differences.

    Args:
        content: The text to search in
        pattern: The pattern to search for
        ignore_punct_whitespace: If True, ignore punctuation/whitespace differences
        casefold: If True, perform case-insensitive matching
        min_normalized_len: Minimum normalized pattern length to search
        max_matches: Maximum number of matches to return

    Returns:
        List of (start_index, end_index) tuples in the ORIGINAL content.
        Spans are non-overlapping and sorted by position.
    """
    normalized_content, map_content = normalize_for_fuzzy_match(
        content,
        ignore_punct_whitespace=ignore_punct_whitespace,
        casefold=casefold,
    )
    normalized_pattern, _ = normalize_for_fuzzy_match(
        pattern,
        ignore_punct_whitespace=ignore_punct_whitespace,
        casefold=casefold,
    )

    if not normalized_pattern:
        return []
    if len(normalized_pattern) < min_normalized_len:
        return []

    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(normalized_content):
        found = normalized_content.find(normalized_pattern, pos)
        if found < 0:
            break

        start_orig = map_content[found]
        end_orig = map_content[found + len(normalized_pattern) - 1] + 1
        spans.append((start_orig, end_orig))

        if len(spans) >= max_matches:
            break

        # Non-overlapping by default for stability
        pos = found + len(normalized_pattern)

    return spans


def find_approximate_match(
    content: str,
    pattern: str,
    *,
    max_error_rate: float = 0.2,
    min_pattern_len: int = 10,
) -> tuple[int, int, float, str] | None:
    """Find best approximate match using sliding window + similarity.

    This handles cases where the model has slight word errors (e.g. "发言" vs "声音").
    Uses a sliding window approach with SequenceMatcher for similarity scoring.

    Args:
        content: The text to search in
        pattern: The pattern to search for
        max_error_rate: Maximum allowed error rate (0.0 to 1.0)
        min_pattern_len: Minimum normalized pattern length to search

    Returns:
        A tuple of (start, end, similarity, matched_text) if a good match is found,
        or None if no match meets the similarity threshold.
    """
    # Normalize both for comparison
    norm_content, map_content = normalize_for_fuzzy_match(content)
    norm_pattern, _ = normalize_for_fuzzy_match(pattern)

    if len(norm_pattern) < min_pattern_len:
        return None

    pattern_len = len(norm_pattern)
    best_match: tuple[int, int, float, str] | None = None
    best_score = 0.0

    # Sliding window with some tolerance for length variation
    window_min = max(min_pattern_len, int(pattern_len * 0.7))
    window_max = int(pattern_len * 1.3)

    for window_size in range(window_min, window_max + 1):
        for i in range(len(norm_content) - window_size + 1):
            window = norm_content[i:i + window_size]

            # Quick pre-filter: check if at least some characters overlap
            common = set(norm_pattern) & set(window)
            if len(common) < len(set(norm_pattern)) * 0.5:
                continue

            # Calculate similarity
            score = SequenceMatcher(None, norm_pattern, window).ratio()

            if score > best_score:
                best_score = score
                # Map back to original positions
                start_orig = map_content[i]
                end_idx = min(i + window_size - 1, len(map_content) - 1)
                end_orig = map_content[end_idx] + 1
                matched_text = content[start_orig:end_orig]
                best_match = (start_orig, end_orig, score, matched_text)

    # Only return if similarity is above threshold
    min_similarity = 1.0 - max_error_rate
    if best_match and best_match[2] >= min_similarity:
        return best_match

    return None


def build_span_previews(
    content: str,
    spans: list[tuple[int, int]],
    *,
    window: int = 40,
    max_items: int = 3,
) -> list[str]:
    """Build short previews around spans for debugging/hints.

    Args:
        content: The original content
        spans: List of (start, end) tuples
        window: Number of characters to include on each side
        max_items: Maximum number of previews to generate

    Returns:
        List of preview strings around each span
    """
    previews: list[str] = []
    for start, end in spans[:max_items]:
        left = max(0, start - window)
        right = min(len(content), end + window)
        snippet = content[left:right]
        previews.append(snippet)
    return previews


def suggest_similar_lines(
    content: str,
    pattern: str,
    *,
    ignore_punct_whitespace: bool = True,
    max_items: int = 3,
) -> list[str]:
    """Suggest similar lines/paragraphs when direct match fails.

    This function helps provide helpful suggestions when a match fails,
    by finding paragraphs that are similar to the pattern.

    Args:
        content: The content to search
        pattern: The pattern that failed to match
        ignore_punct_whitespace: If True, ignore punctuation/whitespace
        max_items: Maximum number of suggestions to return

    Returns:
        List of similar paragraph snippets
    """
    norm_pat, _ = normalize_for_fuzzy_match(
        pattern,
        ignore_punct_whitespace=ignore_punct_whitespace,
    )
    if not norm_pat:
        return []

    # Use paragraphs first (more stable for novels)
    blocks = [b for b in content.split("\n\n") if b.strip()]
    candidates: list[tuple[float, str]] = []

    for b in blocks:
        snippet = b.strip().replace("\n", " ")
        if not snippet:
            continue
        norm_b, _ = normalize_for_fuzzy_match(
            snippet,
            ignore_punct_whitespace=ignore_punct_whitespace,
        )
        if not norm_b:
            continue

        score = (
            0.999
            if norm_pat in norm_b or norm_b in norm_pat
            else SequenceMatcher(None, norm_pat, norm_b).ratio()
        )

        candidates.append((score, snippet[:160] + ("..." if len(snippet) > 160 else "")))

    candidates.sort(key=lambda x: x[0], reverse=True)
    out = [c[1] for c in candidates[: max_items]]
    # Filter very low similarity
    return [s for s in out if s]


def find_unique_line_span(
    content: str,
    anchor: str,
    *,
    ignore_punct_whitespace: bool = True,
    min_score: float = 0.9,
    min_gap: float = 0.08,
) -> tuple[int, int] | None:
    """Find a unique best-matching paragraph span for anchor.

    This function finds a single, unique paragraph that best matches the anchor,
    with confidence scoring to ensure it's not ambiguous.

    Args:
        content: The content to search
        anchor: The anchor text to match
        ignore_punct_whitespace: If True, ignore punctuation/whitespace
        min_score: Minimum similarity score required
        min_gap: Minimum gap between best and second-best scores

    Returns:
        (start, end) tuple in original content if confident, otherwise None
    """
    norm_anchor, _ = normalize_for_fuzzy_match(
        anchor,
        ignore_punct_whitespace=ignore_punct_whitespace,
    )
    if not norm_anchor:
        return None

    blocks = [b for b in content.split("\n\n") if b.strip()]
    if not blocks:
        return None

    scored: list[tuple[float, str]] = []
    for b in blocks:
        norm_b, _ = normalize_for_fuzzy_match(
            b,
            ignore_punct_whitespace=ignore_punct_whitespace,
        )
        if not norm_b:
            continue
        if norm_anchor in norm_b or norm_b in norm_anchor:
            score = 0.999
        else:
            score = SequenceMatcher(None, norm_anchor, norm_b).ratio()
        scored.append((score, b))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_block = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0

    if best_score < min_score:
        return None
    if (best_score - second_score) < min_gap:
        return None

    # Ensure it maps to a single occurrence
    idx = content.find(best_block)
    if idx < 0:
        return None
    if content.find(best_block, idx + 1) >= 0:
        return None

    return idx, idx + len(best_block)


__all__ = [
    "normalize_for_fuzzy_match",
    "find_fuzzy_spans",
    "find_approximate_match",
    "build_span_previews",
    "suggest_similar_lines",
    "find_unique_line_span",
]
