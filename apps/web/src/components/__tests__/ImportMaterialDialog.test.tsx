import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { ReactNode } from "react";

import { ImportMaterialDialog } from "../ImportMaterialDialog";
import { fileApi } from "../../lib/api";

vi.mock("../../contexts/ProjectContext", () => ({
  useProject: () => ({
    currentProjectId: "project-1",
  }),
}));

vi.mock("../../lib/api", () => ({
  fileApi: {
    getTree: vi.fn(),
  },
}));

vi.mock("../../lib/materialsApi", () => ({
  materialsApi: {
    importToProject: vi.fn(),
  },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("../ui/Modal", () => {
  const Modal = ({ open, children }: { open: boolean; children: ReactNode }) =>
    open ? <div>{children}</div> : null;

  Modal.Header = ({ children }: { children: ReactNode }) => <div>{children}</div>;
  Modal.Body = ({ children }: { children: ReactNode }) => <div>{children}</div>;
  Modal.Footer = ({ children }: { children: ReactNode }) => <div>{children}</div>;

  return {
    default: Modal,
  };
});

describe("ImportMaterialDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fileApi.getTree).mockResolvedValue({
      tree: [
        { id: "folder-1", title: "Other Folder", file_type: "folder" },
      ],
    } as never);
  });

  it("resets target folder when dialog reopens without a recommended folder", async () => {
    const preview = {
      title: "Character Preview",
      markdown: "content",
      novel_title: "Novel",
      suggested_file_type: "character",
      suggested_folder_name: "Characters",
      suggested_file_name: "Hero-reference",
    };

    const { rerender } = render(
      <ImportMaterialDialog
        isOpen
        onClose={vi.fn()}
        preview={preview}
        novelId={1}
        entityType="characters"
        entityId={1}
        onSuccess={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(fileApi.getTree).toHaveBeenCalledTimes(1);
    });

    const folderSelect = screen.getByRole("combobox");
    fireEvent.change(folderSelect, { target: { value: "folder-1" } });
    expect(folderSelect).toHaveValue("folder-1");

    rerender(
      <ImportMaterialDialog
        isOpen={false}
        onClose={vi.fn()}
        preview={preview}
        novelId={1}
        entityType="characters"
        entityId={1}
        onSuccess={vi.fn()}
      />
    );

    rerender(
      <ImportMaterialDialog
        isOpen
        onClose={vi.fn()}
        preview={preview}
        novelId={1}
        entityType="characters"
        entityId={1}
        onSuccess={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(fileApi.getTree).toHaveBeenCalledTimes(2);
      expect(screen.getByRole("combobox")).toHaveValue("");
    });
  });
});
