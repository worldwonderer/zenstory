import { render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockNavigate = vi.fn();
const mockGet = vi.fn();
const mockGetTree = vi.fn();
const mockGetChapter = vi.fn();
const mockGetCharacters = vi.fn();
const mockGetStories = vi.fn();
const mockGetPlots = vi.fn();
const mockGetStoryLines = vi.fn();
const mockGetRelationships = vi.fn();
const mockGetGoldenFingers = vi.fn();
const mockGetWorldView = vi.fn();
const mockGetTimeline = vi.fn();
const materialsConfigState = vi.hoisted(() => ({
  relationshipsEnabled: false,
}));
const mediaState = vi.hoisted(() => ({
  isMobile: false,
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ novelId: "novel-1" }),
  };
});

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (
      key: string,
      defaultValueOrOptions?: string | Record<string, unknown>,
    ) => {
      if (typeof defaultValueOrOptions === "string") return defaultValueOrOptions;
      if (
        defaultValueOrOptions &&
        typeof defaultValueOrOptions === "object" &&
        "defaultValue" in defaultValueOrOptions &&
        typeof defaultValueOrOptions.defaultValue === "string"
      ) {
        return defaultValueOrOptions.defaultValue;
      }
      return key;
    },
  }),
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useIsMobile: () => mediaState.isMobile,
}));

vi.mock("../../config/materials", () => ({
  materialsConfig: {
    get relationshipsEnabled() {
      return materialsConfigState.relationshipsEnabled;
    },
  },
}));

vi.mock("../../lib/materialsApi", () => ({
  materialsApi: {
    get: () => mockGet(),
    getTree: () => mockGetTree(),
    getChapter: (...args: unknown[]) => mockGetChapter(...args),
    getCharacters: () => mockGetCharacters(),
    getStories: () => mockGetStories(),
    getPlots: () => mockGetPlots(),
    getStoryLines: () => mockGetStoryLines(),
    getRelationships: () => mockGetRelationships(),
    getGoldenFingers: () => mockGetGoldenFingers(),
    getWorldView: () => mockGetWorldView(),
    getTimeline: () => mockGetTimeline(),
  },
}));

import MaterialDetailPage from "../MaterialDetailPage";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe("MaterialDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    materialsConfigState.relationshipsEnabled = false;
    mediaState.isMobile = false;
    mockGetTree.mockResolvedValue({
      tree: [{ id: "chapter-node-1", type: "chapter" }],
    });
    mockGetChapter.mockResolvedValue({
      id: "chapter-1",
      title: "Opening Chapter",
      chapter_number: 1,
      word_count: 1200,
      summary: "Chapter summary",
      content: "Chapter body",
    });
    mockGetCharacters.mockResolvedValue([
      {
        id: "character-1",
        name: "Li Wei",
        aliases: ["Blade"],
        description: "A fearless lead",
        first_appearance_chapter: 1,
      },
    ]);
    mockGetStories.mockResolvedValue([
      {
        id: "story-1",
        title: "Main arc",
        synopsis: "Story synopsis",
        story_type: "Adventure",
        core_objective: "Save the city",
        core_conflict: "Enemy invasion",
        themes: "[\"hope\",\"sacrifice\"]",
        chapter_range: "1-5",
      },
    ]);
    mockGetPlots.mockResolvedValue([
      {
        id: 1,
        description: "Hidden betrayal",
        plot_type: "Twist",
        characters: ["Li Wei", "Mentor"],
      },
    ]);
    mockGetStoryLines.mockResolvedValue([
      {
        id: 1,
        title: "Revenge path",
        description: "A revenge storyline",
        main_characters: ["Li Wei"],
        themes: ["justice"],
        stories_count: 2,
      },
    ]);
    mockGetRelationships.mockResolvedValue([
      {
        id: 1,
        character_a_name: "Li Wei",
        character_b_name: "Mentor",
      },
    ]);
    mockGetGoldenFingers.mockResolvedValue([
      {
        id: 1,
        name: "Phoenix Core",
      },
    ]);
    mockGetWorldView.mockResolvedValue({
      id: 1,
      power_system: "Qi",
      world_structure: "Three realms",
      key_forces: ["Court"],
    });
    mockGetTimeline.mockResolvedValue([
      {
        id: 1,
        time_tag: "Year 1",
        rel_order: 1,
      },
    ]);
    mockGet.mockResolvedValue({
      id: "novel-1",
      title: "Novel One",
      status: "completed",
      chapters_count: 0,
      characters_count: 0,
      story_lines_count: 0,
      golden_fingers_count: 0,
      has_world_view: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
  });

  it("hides relationships folder by default", async () => {
    render(<MaterialDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    expect(screen.queryByText("materials:detail.relationships")).not.toBeInTheDocument();
  });

  it("shows relationships folder when relationships UI is enabled", async () => {
    materialsConfigState.relationshipsEnabled = true;

    render(<MaterialDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    expect(screen.getByText("materials:detail.relationships")).toBeInTheDocument();
  });

  it("loads folder content and renders chapter, character, and story details", async () => {
    render(<MaterialDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.chapters/ }));
    await waitFor(() => {
      expect(screen.getByText("Opening Chapter")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Opening Chapter/ }));
    expect(await screen.findByText("Chapter summary")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.characters/ }));
    await waitFor(() => {
      expect(screen.getByText("Li Wei")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Li Wei/ }));
    expect(await screen.findByText("A fearless lead")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.stories/ }));
    await waitFor(() => {
      expect(screen.getByText("Main arc")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Main arc/ }));
    expect(await screen.findByText("Story synopsis")).toBeInTheDocument();
    expect(screen.getByText("Save the city")).toBeInTheDocument();
  });

  it("loads plot, storyline, worldview, timeline, and goldenfinger folders", async () => {
    materialsConfigState.relationshipsEnabled = true;
    render(<MaterialDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.plots/ }));
    await waitFor(() => {
      expect(screen.getByText(/Hidden betrayal/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.storylines/ }));
    await waitFor(() => {
      expect(screen.getByText("Revenge path")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.worldview/ }));
    await waitFor(() => {
      expect(screen.getByText("materials:detail.worldviewItem")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.timeline/ }));
    await waitFor(() => {
      expect(screen.getByText("Year 1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.goldenfingers/ }));
    await waitFor(() => {
      expect(screen.getByText("Phoenix Core")).toBeInTheDocument();
    });

    expect(screen.getByText("materials:detail.relationships")).toBeInTheDocument();
  });

  it("renders loading and not-found states", async () => {
    mockGet.mockImplementationOnce(() => new Promise(() => {}));
    const { unmount } = render(<MaterialDetailPage />, { wrapper: createWrapper() });
    expect(document.querySelector(".animate-spin")).toBeInTheDocument();
    unmount();

    mockGet.mockResolvedValueOnce(null);
    render(<MaterialDetailPage />, { wrapper: createWrapper() });
    expect(await screen.findByText("materials:detail.notFound")).toBeInTheDocument();
  });

  it("supports mobile search and detail switching", async () => {
    mediaState.isMobile = true;
    render(<MaterialDetailPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("materials:detail.searchPlaceholder"), {
      target: { value: "char" },
    });
    expect(screen.getByRole("button", { name: /materials:detail.characters/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /materials:detail.chapters/ })).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("materials:detail.searchPlaceholder"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: /materials:detail.characters/ }));
    await waitFor(() => {
      expect(screen.getByText("Li Wei")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Li Wei/ }));
    expect(await screen.findByText("A fearless lead")).toBeInTheDocument();
  });

  it("renders relationship, worldview, timeline, and goldenfinger details", async () => {
    materialsConfigState.relationshipsEnabled = true;
    mockGetRelationships.mockResolvedValueOnce([
      {
        id: 1,
        character_a_name: "Li Wei",
        character_b_name: "Mentor",
        relationship_type: "Ally",
        sentiment: "Trust",
        description: "Their bond evolves",
      },
    ]);
    mockGetGoldenFingers.mockResolvedValueOnce([
      {
        id: 1,
        name: "Phoenix Core",
        type: "Artifact",
        description: "Stores ancient power",
        evolution_history: [
          { stage: "Dormant", description: "Sleeping", chapter: "12", timestamp: "Dawn" },
        ],
      },
    ]);
    mockGetWorldView.mockResolvedValueOnce({
      id: 1,
      power_system: "Qi",
      world_structure: "Three realms",
      key_factions: [{ name: "Court", description: "Rules the empire", leader: "Emperor", territory: "Capital" }],
      special_rules: "No magic after dusk",
    });
    mockGetTimeline.mockResolvedValueOnce([
      {
        id: 1,
        time_tag: "Year 1",
        rel_order: 1,
        uncertain: true,
        chapter_title: "Opening Chapter",
        plot_description: "The turning point",
      },
    ]);

    render(<MaterialDetailPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText("Novel One")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.relationships/ }));
    await waitFor(() => {
      expect(screen.getByText(/Li Wei - Mentor/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Li Wei - Mentor/ }));
    expect(await screen.findByText("Trust")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.goldenfingers/ }));
    await waitFor(() => {
      expect(screen.getByText("Phoenix Core")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Phoenix Core/ }));
    expect(await screen.findByText("Dormant")).toBeInTheDocument();
    expect(screen.getByText("Sleeping")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.worldview/ }));
    await waitFor(() => {
      expect(screen.getByText("materials:detail.worldviewItem")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /materials:detail.worldviewItem/ }));
    expect(await screen.findByText("Court")).toBeInTheDocument();
    expect(screen.getByText("No magic after dusk")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /materials:detail.timeline/ }));
    await waitFor(() => {
      expect(screen.getByText("Year 1")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Year 1/ }));
    expect(await screen.findByText("Opening Chapter")).toBeInTheDocument();
    expect(screen.getByText("The turning point")).toBeInTheDocument();
  });
});
