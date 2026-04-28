/**
 * Natural polish helpers.
 *
 * Prompt selection lives on the server so every client path shares the same
 * authoritative rewrite instructions.
 */

export function preserveSelectionWhitespace(
  originalSelection: string,
  rewrittenText: string,
): string {
  const leading = originalSelection.match(/^\s*/)?.[0] ?? "";
  const trailing = originalSelection.match(/\s*$/)?.[0] ?? "";
  return `${leading}${rewrittenText.trim()}${trailing}`;
}
