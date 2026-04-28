import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { LazyMarkdown } from "../components/LazyMarkdown";
import {
  ChevronLeft,
  Search,
  Folder,
  FolderOpen,
  File,
  User,
  BookOpen,
  Sparkles,
  Globe,
  Zap,
  ChevronRight,
  ChevronDown,
  GitBranch,
  Users,
  Clock,
  Loader2,
} from "../components/icons";
import { materialsApi } from "../lib/materialsApi";
import type {
  MaterialNovel,
  MaterialChapter,
  MaterialCharacter,
  MaterialStory,
  MaterialPlot,
  MaterialStoryLine,
  MaterialCharacterRelationship,
  MaterialGoldenFinger,
  MaterialWorldView,
  MaterialEventTimeline,
} from "../lib/materialsApi";
import { useIsMobile } from "../hooks/useMediaQuery";
import { materialsConfig } from "../config/materials";

type TreeItemType =
  | "folder"
  | "chapter"
  | "character"
  | "story"
  | "worldview"
  | "cheat"
  | "plot"
  | "storyline"
  | "relationship"
  | "goldenfinger"
  | "timeline";

interface TreeItem {
  id: string;
  type: TreeItemType;
  title: string;
  children?: TreeItem[];
  data?: unknown;
}

export default function MaterialDetailPage() {
  const { novelId } = useParams<{ novelId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation(["materials", "common"]);
  const isMobile = useIsMobile();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedItem, setSelectedItem] = useState<TreeItem | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [loadedFolders, setLoadedFolders] = useState<Set<string>>(new Set());
  // 移动端：是否显示内容详情（false = 显示文件树）
  const [showMobileContent, setShowMobileContent] = useState(false);

  // Fetch material details
  const { data: material, isLoading: materialLoading } = useQuery({
    queryKey: ["material", novelId],
    queryFn: () => materialsApi.get(novelId!),
    enabled: !!novelId,
    staleTime: 30 * 1000,
  });

  // Fetch chapters
  const { data: chapters = [], refetch: refetchChapters, isFetching: isFetchingChapters } = useQuery({
    queryKey: ["material-chapters", novelId],
    queryFn: async () => {
      const tree = await materialsApi.getTree(novelId!);
      const chapterNodes = tree.tree.filter((node) => node.type === "chapter");
      const chapterDetails = await Promise.all(
        chapterNodes.map((node) => materialsApi.getChapter(novelId!, node.id))
      );
      return chapterDetails;
    },
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch characters
  const { data: characters = [], refetch: refetchCharacters, isFetching: isFetchingCharacters } = useQuery({
    queryKey: ["material-characters", novelId],
    queryFn: () => materialsApi.getCharacters(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch stories
  const { data: stories = [], refetch: refetchStories, isFetching: isFetchingStories } = useQuery({
    queryKey: ["material-stories", novelId],
    queryFn: () => materialsApi.getStories(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch plots
  const { data: plots = [], refetch: refetchPlots, isFetching: isFetchingPlots } = useQuery({
    queryKey: ["material-plots", novelId],
    queryFn: () => materialsApi.getPlots(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch storylines
  const { data: storylines = [], refetch: refetchStorylines, isFetching: isFetchingStorylines } = useQuery({
    queryKey: ["material-storylines", novelId],
    queryFn: () => materialsApi.getStoryLines(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch relationships
  const { data: relationships = [], refetch: refetchRelationships, isFetching: isFetchingRelationships } = useQuery({
    queryKey: ["material-relationships", novelId],
    queryFn: () => materialsApi.getRelationships(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch golden fingers
  const { data: goldenFingers = [], refetch: refetchGoldenFingers, isFetching: isFetchingGoldenFingers } = useQuery({
    queryKey: ["material-goldenfingers", novelId],
    queryFn: () => materialsApi.getGoldenFingers(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch worldview
  const { data: worldview, refetch: refetchWorldview, isFetching: isFetchingWorldview } = useQuery({
    queryKey: ["material-worldview", novelId],
    queryFn: () => materialsApi.getWorldView(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Fetch timeline
  const { data: timeline = [], refetch: refetchTimeline, isFetching: isFetchingTimeline } = useQuery({
    queryKey: ["material-timeline", novelId],
    queryFn: () => materialsApi.getTimeline(novelId!),
    enabled: false,
    staleTime: 30 * 1000,
  });

  // Loading states mapping
  const loadingStates: Record<string, boolean> = {
    chapters: isFetchingChapters,
    characters: isFetchingCharacters,
    stories: isFetchingStories,
    plots: isFetchingPlots,
    storylines: isFetchingStorylines,
    relationships: isFetchingRelationships,
    goldenfingers: isFetchingGoldenFingers,
    worldview: isFetchingWorldview,
    timeline: isFetchingTimeline,
  };

  // Trigger load function
  const triggerLoad = (folderId: string) => {
    if (loadedFolders.has(folderId)) return;

    setLoadedFolders((prev) => new Set(prev).add(folderId));

    switch (folderId) {
      case "chapters":
        refetchChapters();
        break;
      case "characters":
        refetchCharacters();
        break;
      case "stories":
        refetchStories();
        break;
      case "plots":
        refetchPlots();
        break;
      case "storylines":
        refetchStorylines();
        break;
      case "relationships":
        refetchRelationships();
        break;
      case "goldenfingers":
        refetchGoldenFingers();
        break;
      case "worldview":
        refetchWorldview();
        break;
      case "timeline":
        refetchTimeline();
        break;
    }
  };

  // Build tree structure - folders always visible, children lazy loaded
  const buildTree = (): TreeItem[] => {
    const tree: TreeItem[] = [];

    // Chapters folder - always show
    tree.push({
      id: "chapters",
      type: "folder",
      title: t("materials:detail.chapters"),
      children: chapters.map((chapter) => ({
        id: chapter.id,
        type: "chapter",
        title: chapter.title || `${t("materials:detail.chapter")} ${chapter.chapter_number}`,
        data: chapter,
      })),
    });

    // Characters folder - always show
    tree.push({
      id: "characters",
      type: "folder",
      title: t("materials:detail.characters"),
      children: characters.map((character) => ({
        id: character.id,
        type: "character",
        title: character.name,
        data: character,
      })),
    });

    // Stories folder - always show
    tree.push({
      id: "stories",
      type: "folder",
      title: t("materials:detail.stories"),
      children: stories.map((story) => ({
        id: story.id,
        type: "story",
        title: story.title,
        data: story,
        metadata: {
          description: story.synopsis,
          plot_type: story.story_type,
        },
      })),
    });

    // Plots folder - always show
    tree.push({
      id: "plots",
      type: "folder",
      title: t("materials:detail.plots"),
      children: plots.map((plot) => ({
        id: String(plot.id),
        type: "plot",
        title: plot.description.substring(0, 50) + (plot.description.length > 50 ? "..." : ""),
        data: plot,
      })),
    });

    // StoryLines folder - always show
    tree.push({
      id: "storylines",
      type: "folder",
      title: t("materials:detail.storylines"),
      children: storylines.map((storyline) => ({
        id: String(storyline.id),
        type: "storyline",
        title: storyline.title,
        data: storyline,
      })),
    });

    if (materialsConfig.relationshipsEnabled) {
      tree.push({
        id: "relationships",
        type: "folder",
        title: t("materials:detail.relationships"),
        children: relationships.map((rel) => ({
          id: String(rel.id),
          type: "relationship",
          title: `${rel.character_a_name} - ${rel.character_b_name}`,
          data: rel,
        })),
      });
    }

    // Golden Fingers folder - always show
    tree.push({
      id: "goldenfingers",
      type: "folder",
      title: t("materials:detail.goldenfingers"),
      children: goldenFingers.map((gf) => ({
        id: String(gf.id),
        type: "goldenfinger",
        title: gf.name,
        data: gf,
      })),
    });

    // Worldview folder - always show
    tree.push({
      id: "worldview",
      type: "folder",
      title: t("materials:detail.worldview"),
      children: worldview ? [{
        id: String(worldview.id),
        type: "worldview",
        title: t("materials:detail.worldviewItem"),
        data: worldview,
      }] : [],
    });

    // Timeline folder - always show
    tree.push({
      id: "timeline",
      type: "folder",
      title: t("materials:detail.timeline"),
      children: timeline.map((event) => ({
        id: String(event.id),
        type: "timeline",
        title: event.time_tag || `#${event.rel_order}`,
        data: event,
      })),
    });

    return tree;
  };

  const treeData = buildTree();

  // Filter tree based on search
  const filterTree = (items: TreeItem[], query: string): TreeItem[] => {
    if (!query) return items;

    return items
      .map((item) => {
        if (item.type === "folder" && item.children) {
          const filteredChildren = filterTree(item.children, query);
          if (filteredChildren.length > 0) {
            return { ...item, children: filteredChildren };
          }
        }

        if (item.title.toLowerCase().includes(query.toLowerCase())) {
          return item;
        }

        return null;
      })
      .filter((item): item is TreeItem => item !== null);
  };

  const filteredTree = filterTree(treeData, searchQuery);

  const toggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
        triggerLoad(folderId);
      }
      return next;
    });
  };

  const handleItemClick = (item: TreeItem) => {
    if (item.type === "folder") {
      toggleFolder(item.id);
    } else {
      setSelectedItem(item);
      // 移动端：选择项目后切换到内容视图
      if (isMobile) {
        setShowMobileContent(true);
      }
    }
  };

  const handleMobileBack = () => {
    setShowMobileContent(false);
  };

  if (materialLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--accent-primary))]" />
      </div>
    );
  }

  if (!material) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-[hsl(var(--text-secondary))]">{t("materials:detail.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-[hsl(var(--bg-primary))]">
      {/* Header */}
      <div className="shrink-0 border-b border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))]">
        <div className={`flex items-center justify-between ${isMobile ? 'px-3 py-2' : 'px-4 py-3'}`}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                if (isMobile && showMobileContent) {
                  handleMobileBack();
                } else {
                  navigate("/dashboard/materials");
                }
              }}
              className="p-2 rounded-lg hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
            >
              <ChevronLeft className="w-5 h-5 text-[hsl(var(--text-secondary))]" />
            </button>
            <div>
              <h1 className={`font-semibold text-[hsl(var(--text-primary))] ${isMobile ? 'text-base' : 'text-lg'}`}>
                {isMobile && showMobileContent && selectedItem ? selectedItem.title : material.title}
              </h1>
              {!(isMobile && showMobileContent) && (
                <p className="text-xs text-[hsl(var(--text-tertiary))]">
                  {material.chapters_count || 0} {t("materials:chapters")}
                </p>
              )}
            </div>
          </div>

          {/* Search - 在移动端内容视图隐藏 */}
          {!(isMobile && showMobileContent) && (
            <div className={`relative ${isMobile ? 'flex-1 ml-3' : 'max-w-xs'}`}>
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--text-tertiary))]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("materials:detail.searchPlaceholder")}
                className={`w-full pl-9 pr-3 py-2 rounded-lg border border-[hsl(var(--border-color))] bg-[hsl(var(--bg-primary))] text-sm focus:outline-none focus:ring-2 focus:ring-[hsl(var(--accent-primary)/0.3)]`}
              />
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {isMobile ? (
          // 移动端：单栏切换布局
          showMobileContent ? (
            // 内容详情视图
            <div className="flex-1 overflow-y-auto">
              <div className="p-4">
                {selectedItem ? (
                  <ContentDetail item={selectedItem} />
                ) : (
                  <EmptyState material={material} />
                )}
              </div>
            </div>
          ) : (
            // 文件树视图
            <div className="flex-1 overflow-y-auto bg-[hsl(var(--bg-secondary))]">
              <div className="p-3">
                <FileTree
                  items={filteredTree}
                  selectedId={selectedItem?.id}
                  expandedFolders={expandedFolders}
                  onItemClick={handleItemClick}
                  loadingStates={loadingStates}
                />
              </div>
            </div>
          )
        ) : (
          // 桌面端：双栏布局
          <>
            {/* Left: File Tree */}
            <div className="w-80 border-r border-[hsl(var(--border-color))] bg-[hsl(var(--bg-secondary))] overflow-y-auto">
              <div className="p-4">
                <FileTree
                  items={filteredTree}
                  selectedId={selectedItem?.id}
                  expandedFolders={expandedFolders}
                  onItemClick={handleItemClick}
                  loadingStates={loadingStates}
                />
              </div>
            </div>

            {/* Right: Content Details */}
            <div className="flex-1 overflow-y-auto">
              <div className="p-6">
                {selectedItem ? (
                  <ContentDetail item={selectedItem} />
                ) : (
                  <EmptyState material={material} />
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// FileTree Component
interface FileTreeProps {
  items: TreeItem[];
  selectedId?: string;
  expandedFolders: Set<string>;
  onItemClick: (item: TreeItem) => void;
  loadingStates: Record<string, boolean>;
  level?: number;
}

function FileTree({ items, selectedId, expandedFolders, onItemClick, loadingStates, level = 0 }: FileTreeProps) {
  const getIcon = (type: TreeItemType, isExpanded: boolean) => {
    switch (type) {
      case "folder":
        return isExpanded ? (
          <FolderOpen className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
        ) : (
          <Folder className="w-4 h-4 text-[hsl(var(--text-tertiary))]" />
        );
      case "chapter":
        return <BookOpen className="w-4 h-4 text-blue-500" />;
      case "character":
        return <User className="w-4 h-4 text-purple-500" />;
      case "story":
        return <Sparkles className="w-4 h-4 text-amber-500" />;
      case "worldview":
        return <Globe className="w-4 h-4 text-green-500" />;
      case "cheat":
        return <Zap className="w-4 h-4 text-red-500" />;
      case "plot":
        return <File className="w-4 h-4 text-cyan-500" />;
      case "storyline":
        return <GitBranch className="w-4 h-4 text-indigo-500" />;
      case "relationship":
        return <Users className="w-4 h-4 text-pink-500" />;
      case "goldenfinger":
        return <Zap className="w-4 h-4 text-yellow-500" />;
      case "timeline":
        return <Clock className="w-4 h-4 text-teal-500" />;
      default:
        return <File className="w-4 h-4 text-[hsl(var(--text-tertiary))]" />;
    }
  };

  return (
    <div className="space-y-1">
      {items.map((item) => {
        const isExpanded = expandedFolders.has(item.id);
        const isSelected = selectedId === item.id;
        const hasChildren = item.children && item.children.length > 0;

        return (
          <div key={item.id}>
            <button
              onClick={() => onItemClick(item)}
              className={`w-full flex items-center gap-2 px-2 py-2.5 rounded-lg text-sm transition-colors ${
                isSelected
                  ? "bg-[hsl(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]"
                  : "hover:bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-primary))] active:bg-[hsl(var(--bg-hover))]"
              }`}
              style={{ paddingLeft: `${level * 12 + 8}px` }}
            >
              {item.type === "folder" && (
                <span className="shrink-0">
                  {isExpanded ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5" />
                  )}
                </span>
              )}
              <span className="shrink-0">{getIcon(item.type, isExpanded)}</span>
              <span className="truncate flex-1 text-left">{item.title}</span>
              {item.type === "folder" && loadingStates[item.id] && (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[hsl(var(--accent-primary))]" />
              )}
              {hasChildren && (
                <span className="text-xs text-[hsl(var(--text-tertiary))]">
                  {item.children!.length}
                </span>
              )}
            </button>

            {item.type === "folder" && isExpanded && hasChildren && (
              <FileTree
                items={item.children!}
                selectedId={selectedId}
                expandedFolders={expandedFolders}
                onItemClick={onItemClick}
                loadingStates={loadingStates}
                level={level + 1}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Markdown 内容渲染组件
function MarkdownContent({ content, className = "" }: { content: string; className?: string }) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none
        prose-headings:text-[hsl(var(--text-primary))]
        prose-p:text-[hsl(var(--text-primary))]
        prose-strong:text-[hsl(var(--text-primary))]
        prose-ul:text-[hsl(var(--text-primary))]
        prose-ol:text-[hsl(var(--text-primary))]
        prose-li:text-[hsl(var(--text-primary))]
        prose-a:text-[hsl(var(--accent-primary))]
        ${className}`}>
      <LazyMarkdown>{content}</LazyMarkdown>
    </div>
  );
}

// ContentDetail Component
interface ContentDetailProps {
  item: TreeItem;
}

function ContentDetail({ item }: ContentDetailProps) {
  const { t } = useTranslation(["materials"]);

  if (item.type === "chapter") {
    const chapter = item.data as MaterialChapter;
    return (
      <div className="max-w-4xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="w-5 h-5 text-blue-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {chapter.title}
            </h2>
          </div>
          <div className="flex items-center gap-4 text-sm text-[hsl(var(--text-secondary))]">
            <span>{t("materials:detail.chapterNumber")}: {chapter.chapter_number}</span>
            <span>{t("materials:detail.wordCount")}: {chapter.word_count?.toLocaleString()}</span>
          </div>
        </div>

        {chapter.summary && (
          <div className="mb-6 p-4 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))]">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.summary")}
            </h3>
            <MarkdownContent content={chapter.summary} />
          </div>
        )}

        {chapter.content && (
          <MarkdownContent content={chapter.content} />
        )}
      </div>
    );
  }

  if (item.type === "character") {
    const character = item.data as MaterialCharacter;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <User className="w-5 h-5 text-purple-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {character.name}
            </h2>
          </div>
          {character.aliases && character.aliases.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-[hsl(var(--text-secondary))]">
              <span>{t("materials:detail.aliases")}:</span>
              <span>{character.aliases.join(", ")}</span>
            </div>
          )}
        </div>

        {character.description && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.description")}
            </h3>
            <MarkdownContent content={character.description} />
          </div>
        )}

        {character.first_appearance_chapter && (
          <div className="text-sm text-[hsl(var(--text-secondary))]">
            {t("materials:detail.firstAppearance")}: {t("materials:detail.chapter")} {character.first_appearance_chapter}
          </div>
        )}
      </div>
    );
  }

  if (item.type === "story") {
    const story = item.data as MaterialStory;

    const parseThemes = (themes: string | null | undefined): string[] => {
      if (!themes) return [];
      if (typeof themes === 'string') {
        try {
          const parsed = JSON.parse(themes);
          return Array.isArray(parsed) ? parsed : [themes];
        } catch {
          return themes.split(',').map(t => t.trim()).filter(Boolean);
        }
      }
      return [];
    };

    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {story.title}
            </h2>
          </div>
          {story.story_type && (
            <span className="inline-block px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
              {story.story_type}
            </span>
          )}
        </div>

        <div className="mb-6">
          <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
            {t("materials:detail.description")}
          </h3>
          <MarkdownContent content={story.synopsis} />
        </div>

        {story.core_objective && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.coreObjective")}
            </h3>
            <MarkdownContent content={story.core_objective} />
          </div>
        )}

        {story.core_conflict && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.coreConflict")}
            </h3>
            <MarkdownContent content={story.core_conflict} />
          </div>
        )}

        {story.themes && parseThemes(story.themes).length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.themes")}
            </h3>
            <div className="flex flex-wrap gap-2">
              {parseThemes(story.themes).map((theme, index) => (
                <span
                  key={index}
                  className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium"
                >
                  {theme}
                </span>
              ))}
            </div>
          </div>
        )}

        {story.chapter_range && (
          <div>
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.relatedChapters")}
            </h3>
            <div className="flex flex-wrap gap-2">
              <span
                className="px-3 py-1 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] text-sm text-[hsl(var(--text-primary))]"
              >
                {t("materials:detail.chapter")} {story.chapter_range}
              </span>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (item.type === "plot") {
    const plot = item.data as MaterialPlot;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <File className="w-5 h-5 text-cyan-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {t("materials:detail.plotTitle")}
            </h2>
          </div>
          <span className="inline-block px-3 py-1 rounded-full bg-cyan-100 text-cyan-700 text-xs font-medium">
            {plot.plot_type}
          </span>
        </div>

        <div className="mb-6">
          <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
            {t("materials:detail.description")}
          </h3>
          <MarkdownContent content={plot.description} />
        </div>

        {plot.characters && plot.characters.length > 0 && (
          <div>
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.involvedCharacters")}
            </h3>
            <div className="flex flex-wrap gap-2">
              {plot.characters.map((char: string, index: number) => (
                <span
                  key={index}
                  className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-medium"
                >
                  {char}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (item.type === "storyline") {
    const storyline = item.data as MaterialStoryLine;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <GitBranch className="w-5 h-5 text-indigo-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {storyline.title}
            </h2>
          </div>
        </div>

        {storyline.description && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.description")}
            </h3>
            <MarkdownContent content={storyline.description} />
          </div>
        )}

        {storyline.main_characters && storyline.main_characters.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.mainCharacters")}
            </h3>
            <div className="flex flex-wrap gap-2">
              {storyline.main_characters.map((char: string, index: number) => (
                <span
                  key={index}
                  className="px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-medium"
                >
                  {char}
                </span>
              ))}
            </div>
          </div>
        )}

        {storyline.themes && storyline.themes.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.themes")}
            </h3>
            <div className="flex flex-wrap gap-2">
              {storyline.themes.map((theme: string, index: number) => (
                <span
                  key={index}
                  className="px-3 py-1 rounded-full bg-indigo-100 text-indigo-700 text-xs font-medium"
                >
                  {theme}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="text-sm text-[hsl(var(--text-secondary))]">
          {t("materials:detail.storiesCount")}: {storyline.stories_count}
        </div>
      </div>
    );
  }

  if (item.type === "relationship") {
    const relationship = item.data as MaterialCharacterRelationship;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-5 h-5 text-pink-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {relationship.character_a_name} - {relationship.character_b_name}
            </h2>
          </div>
          <span className="inline-block px-3 py-1 rounded-full bg-pink-100 text-pink-700 text-xs font-medium">
            {relationship.relationship_type}
          </span>
        </div>

        {relationship.sentiment && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.sentiment")}
            </h3>
            <MarkdownContent content={relationship.sentiment} />
          </div>
        )}

        {relationship.description && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.description")}
            </h3>
            <MarkdownContent content={relationship.description} />
          </div>
        )}
      </div>
    );
  }

  if (item.type === "goldenfinger") {
    const goldenfinger = item.data as MaterialGoldenFinger;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-5 h-5 text-yellow-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {goldenfinger.name}
            </h2>
          </div>
          <span className="inline-block px-3 py-1 rounded-full bg-[hsl(var(--warning)/0.2)] text-[hsl(var(--warning))] text-xs font-medium">
            {goldenfinger.type}
          </span>
        </div>

        {goldenfinger.description && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.description")}
            </h3>
            <MarkdownContent content={goldenfinger.description} />
          </div>
        )}

        {goldenfinger.evolution_history && goldenfinger.evolution_history.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.evolutionHistory")}
            </h3>
            <div className="space-y-3">
              {goldenfinger.evolution_history.map((item, index) => (
                <div
                  key={index}
                  className="p-4 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))]"
                >
                  {item.stage && (
                    <h4 className="font-semibold text-[hsl(var(--text-primary))] mb-2">
                      {item.stage}
                    </h4>
                  )}
                  {item.description && (
                    <div className="mb-2">
                      <MarkdownContent content={item.description} className="text-sm" />
                    </div>
                  )}
                  <div className="flex flex-wrap gap-3 text-xs text-[hsl(var(--text-tertiary))]">
                    {item.chapter && (
                      <span>
                        <span className="font-medium">{t("materials:detail.chapterLabel")}:</span> {item.chapter}
                      </span>
                    )}
                    {item.timestamp && (
                      <span>
                        <span className="font-medium">Time:</span> {item.timestamp}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  if (item.type === "worldview") {
    const worldview = item.data as MaterialWorldView;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Globe className="w-5 h-5 text-green-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {t("materials:detail.worldview")}
            </h2>
          </div>
        </div>

        {worldview.power_system && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.powerSystem")}
            </h3>
            <MarkdownContent content={worldview.power_system} />
          </div>
        )}

        {worldview.world_structure && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.worldStructure")}
            </h3>
            <MarkdownContent content={worldview.world_structure} />
          </div>
        )}

        {worldview.key_factions && worldview.key_factions.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.keyFactions")}
            </h3>
            <div className="space-y-3">
              {worldview.key_factions.map((faction, index) => (
                <div
                  key={index}
                  className="p-4 rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))]"
                >
                  <h4 className="font-semibold text-[hsl(var(--text-primary))] mb-2">
                    {faction.name}
                  </h4>
                  {faction.description && (
                    <div className="mb-2">
                      <MarkdownContent content={faction.description} className="text-sm" />
                    </div>
                  )}
                  <div className="flex flex-wrap gap-3 text-xs text-[hsl(var(--text-tertiary))]">
                    {faction.leader && (
                      <span>
                        <span className="font-medium">{t("materials:detail.leader")}:</span> {faction.leader}
                      </span>
                    )}
                    {faction.territory && (
                      <span>
                        <span className="font-medium">{t("materials:detail.territory")}:</span> {faction.territory}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {worldview.special_rules && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.specialRules")}
            </h3>
            <MarkdownContent content={worldview.special_rules} />
          </div>
        )}
      </div>
    );
  }

  if (item.type === "timeline") {
    const event = item.data as MaterialEventTimeline;
    return (
      <div className="max-w-3xl">
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-5 h-5 text-teal-500" />
            <h2 className="text-2xl font-bold text-[hsl(var(--text-primary))]">
              {t("materials:detail.timelineEvent")}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-[hsl(var(--text-secondary))]">
              {t("materials:detail.sequence")}: {event.rel_order}
            </span>
            {event.uncertain && (
              <span className="inline-block px-2 py-0.5 rounded-full bg-[hsl(var(--warning)/0.2)] text-[hsl(var(--warning))] text-xs font-medium">
                {t("materials:detail.uncertain")}
              </span>
            )}
          </div>
        </div>

        {event.time_tag && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.timeTag")}
            </h3>
            <p className="text-sm text-[hsl(var(--text-primary))]">
              {event.time_tag}
            </p>
          </div>
        )}

        <div className="mb-6">
          <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
            {t("materials:detail.relatedChapter")}
          </h3>
          <p className="text-sm text-[hsl(var(--text-primary))]">
            {event.chapter_title}
          </p>
        </div>

        {event.plot_description && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-[hsl(var(--text-secondary))] mb-2">
              {t("materials:detail.relatedPlot")}
            </h3>
            <MarkdownContent content={event.plot_description} />
          </div>
        )}
      </div>
    );
  }

  return null;
}

// EmptyState Component
interface EmptyStateProps {
  material: MaterialNovel;
}

function EmptyState({ material }: EmptyStateProps) {
  const { t } = useTranslation(["materials"]);

  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-12">
      <div className="w-16 h-16 rounded-2xl bg-[hsl(var(--accent-primary)/0.1)] flex items-center justify-center mb-4">
        <BookOpen className="w-8 h-8 text-[hsl(var(--accent-primary))]" />
      </div>
      <h3 className="text-lg font-semibold text-[hsl(var(--text-primary))] mb-2">
        {t("materials:detail.emptyTitle")}
      </h3>
      <p className="text-sm text-[hsl(var(--text-secondary))] max-w-md">
        {t("materials:detail.emptyDescription")}
      </p>

      {material.status === "processing" && (
        <div className="mt-6 flex items-center gap-2 text-sm text-blue-600">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
          <span>{t("materials:status.processing")}</span>
        </div>
      )}
    </div>
  );
}
