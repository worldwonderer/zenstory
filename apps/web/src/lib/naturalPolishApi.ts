/**
 * Natural polish API (single-round HTTP request).
 *
 * Replaces the previous streaming agent request for "去 AI 味" rewrites.
 *
 * Contract:
 * - POST /api/v1/editor/natural-polish
 * - Supports AbortSignal cancellation
 * - Returns rewritten plain text (JSON: { text: string })
 */

import { api } from "./apiClient";

export interface NaturalPolishParams {
  projectId: string;
  fileId: string;
  fileType?: string;
  selectedText: string;
}

type NaturalPolishResponse = {
  text: string;
};

function extractText(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") {
    throw new Error("Invalid natural polish response");
  }
  const data = payload as Record<string, unknown>;
  if (typeof data.text === "string") return data.text;
  throw new Error("Invalid natural polish response");
}

export const naturalPolishApi = {
  naturalPolish: async (
    params: NaturalPolishParams,
    opts?: { signal?: AbortSignal },
  ): Promise<string> => {
    const payload = {
      project_id: params.projectId,
      selected_text: params.selectedText,
      metadata: {
        current_file_id: params.fileId,
        current_file_type: params.fileType,
        source: "editor_natural_polish",
      },
    };

    const result = await api.post<NaturalPolishResponse | string>(
      "/api/v1/editor/natural-polish",
      payload,
      { signal: opts?.signal },
    );
    return extractText(result);
  },
};
