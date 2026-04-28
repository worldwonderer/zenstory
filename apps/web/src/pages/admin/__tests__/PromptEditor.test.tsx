import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import PromptEditor from "../PromptEditor";

const useQueryMock = vi.fn();
const useMutationMock = vi.fn();
const invalidateQueriesMock = vi.fn();
const navigateMock = vi.fn();
const saveMutateMock = vi.fn();
const deleteMutateMock = vi.fn();

let projectTypeParam = "new";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
  useParams: () => ({ projectType: projectTypeParam }),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: (...args: unknown[]) => useQueryMock(...args),
  useMutation: (...args: unknown[]) => useMutationMock(...args),
  useQueryClient: () => ({
    invalidateQueries: invalidateQueriesMock,
  }),
}));

vi.mock("../../../lib/toast", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("PromptEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useMutationMock.mockImplementation(
      ({ mutationFn }: { mutationFn?: (...args: unknown[]) => unknown }) => {
        const source = mutationFn?.toString() ?? "";
        if (source.includes("deletePrompt")) {
          return { mutate: deleteMutateMock, isPending: false };
        }
        return { mutate: saveMutateMock, isPending: false };
      }
    );
  });

  it("shows loading state while existing prompt is loading", () => {
    projectTypeParam = "novel";
    useQueryMock.mockReturnValue({ data: undefined, isLoading: true });

    const { container } = render(<PromptEditor />);
    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });

  it("submits save payload for new prompt", () => {
    projectTypeParam = "new";
    useQueryMock.mockReturnValue({ data: undefined, isLoading: false });

    render(<PromptEditor />);

    fireEvent.click(screen.getByRole("button", { name: "promptEditor.save" }));

    expect(saveMutateMock).toHaveBeenCalledWith({
      role_definition: "",
      capabilities: "",
      directory_structure: "",
      content_structure: "",
      file_types: "",
      writing_guidelines: "",
      include_dialogue_guidelines: false,
      primary_content_type: "novel",
      is_active: true,
    });
  });

  it("loads existing config and submits save", () => {
    projectTypeParam = "novel";
    useQueryMock.mockReturnValue({
      data: {
        project_type: "novel",
        role_definition: "existing role",
        capabilities: "existing capabilities",
        directory_structure: "existing directory",
        content_structure: "existing content",
        file_types: "existing file types",
        writing_guidelines: "existing guidelines",
        include_dialogue_guidelines: true,
        primary_content_type: "novel",
        is_active: true,
      },
      isLoading: false,
    });

    render(<PromptEditor />);

    fireEvent.click(screen.getByRole("button", { name: "promptEditor.save" }));

    expect(saveMutateMock).toHaveBeenCalledWith(
      expect.objectContaining({
        role_definition: "existing role",
        include_dialogue_guidelines: true,
      })
    );
  });

  it("confirms and triggers delete for existing prompt", () => {
    projectTypeParam = "novel";
    useQueryMock.mockReturnValue({
      data: {
        project_type: "novel",
        role_definition: "",
        capabilities: "",
        directory_structure: "",
        content_structure: "",
        file_types: "",
        writing_guidelines: "",
        include_dialogue_guidelines: false,
        primary_content_type: "novel",
        is_active: true,
      },
      isLoading: false,
    });

    render(<PromptEditor />);

    fireEvent.click(screen.getAllByRole("button", { name: "prompts.delete" })[0]);
    expect(screen.getByText("prompts.deleteConfirm")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "common:confirm" }));
    expect(deleteMutateMock).toHaveBeenCalledTimes(1);
  });
});
