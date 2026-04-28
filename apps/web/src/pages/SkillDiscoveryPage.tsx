import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LazyMarkdown } from "../components/LazyMarkdown";
import { logger } from "../lib/logger";
import {
  ArrowLeft,
  Search,
  Plus,
  Check,
  Zap,
  ChevronDown,
  ChevronUp,
  Users,
  Shield,
} from "../components/icons";
import { publicSkillsApi } from "../lib/api";
import type { PublicSkill, SkillCategory } from "../types";
import { useIsMobile, useIsTablet } from "../hooks/useMediaQuery";

export default function SkillDiscoveryPage() {
  const { t } = useTranslation(["skills", "common"]);
  const isMobile = useIsMobile();
  const isTablet = useIsTablet();

  const [skills, setSkills] = useState<PublicSkill[]>([]);
  const [categories, setCategories] = useState<SkillCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [addingId, setAddingId] = useState<string | null>(null);

  const pageSize = 12;

  const loadCategories = useCallback(async () => {
    try {
      const response = await publicSkillsApi.getCategories();
      setCategories(response.categories);
    } catch (error) {
      logger.error("Failed to load categories:", error);
    }
  }, []);

  const loadSkills = useCallback(async () => {
    try {
      // Only show loading spinner on initial load
      if (isInitialLoad) {
        setLoading(true);
      }
      const response = await publicSkillsApi.list({
        category: selectedCategory || undefined,
        search: searchQuery || undefined,
        page,
        page_size: pageSize,
      });
      setSkills(response.skills);
      setTotal(response.total);
    } catch (error) {
      logger.error("Failed to load skills:", error);
    } finally {
      if (isInitialLoad) {
        setLoading(false);
        setIsInitialLoad(false);
      }
    }
  }, [isInitialLoad, page, searchQuery, selectedCategory]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    loadSkills();
  }, [selectedCategory, searchQuery, page, loadSkills]);

  const handleAdd = async (skillId: string) => {
    try {
      setAddingId(skillId);
      const result = await publicSkillsApi.add(skillId);
      // Update local state to show as added
      setSkills((prev) =>
        prev.map((s) => {
          if (s.id !== skillId) return s;
          if (result.success) {
            return { ...s, is_added: true, add_count: s.add_count + 1 };
          }
          if (result.added_skill_id) {
            return { ...s, is_added: true };
          }
          return s;
        })
      );
    } catch (error) {
      logger.error("Failed to add skill:", error);
    } finally {
      setAddingId(null);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadSkills();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      {/* Header */}
      <div className={`${isMobile ? "mb-4" : isTablet ? "mb-6" : "mb-8"}`}>
        <div className="flex items-center gap-3 mb-2">
          <Link
            to="/dashboard/skills"
            className="p-2 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1
              className={`font-bold text-[hsl(var(--text-primary))] ${
                isTablet ? "text-2xl" : "text-2xl"
              }`}
            >
              {t("skills:discover")}
            </h1>
            <p
              className={`text-[hsl(var(--text-secondary))] ${
                isTablet ? "text-sm" : "text-sm"
              }`}
            >
              {t("skills:discoverDescription")}
            </p>
          </div>
        </div>
      </div>

      {/* Search and Filter */}
      <div className={`flex flex-col gap-4 ${isMobile ? "mb-4" : "mb-6"}`}>
        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[hsl(var(--text-tertiary))]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("skills:searchPlaceholder")}
              className="input pl-10 w-full"
            />
          </div>
          <button type="submit" className="btn-primary px-4">
            {t("common:search")}
          </button>
        </form>

        {/* Category Filter */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setSelectedCategory("");
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
              selectedCategory === ""
                ? "bg-[hsl(var(--accent-primary))] text-white"
                : "bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))]"
            }`}
          >
            {t("skills:allCategories")}
          </button>
          {categories.map((cat) => (
            <button
              key={cat.name}
              onClick={() => {
                setSelectedCategory(cat.name);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                selectedCategory === cat.name
                  ? "bg-[hsl(var(--accent-primary))] text-white"
                  : "bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-hover))]"
              }`}
            >
              {cat.name} ({cat.count})
            </button>
          ))}
        </div>
      </div>

      {/* Skills Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[hsl(var(--accent-primary))]" />
        </div>
      ) : skills.length === 0 ? (
        <div
          className={`text-center bg-[hsl(var(--bg-secondary))] rounded-2xl border border-[hsl(var(--border-color))] ${
            isMobile ? "py-8 px-4" : "py-12"
          }`}
        >
          <Zap
            className={`mx-auto mb-3 text-[hsl(var(--text-tertiary))] opacity-50 ${
              isMobile ? "w-10 h-10" : "w-12 h-12"
            }`}
          />
          <p className="text-[hsl(var(--text-secondary))]">
            {t("skills:noSkillsFound")}
          </p>
        </div>
      ) : (
        <>
          <div
            className={`grid gap-4 ${
              isMobile
                ? "grid-cols-1"
                : isTablet
                ? "grid-cols-2"
                : "grid-cols-3"
            }`}
          >
            {skills.map((skill) => (
              <DiscoverySkillCard
                key={skill.id}
                skill={skill}
                onAdd={() => handleAdd(skill.id)}
                adding={addingId === skill.id}
                isMobile={isMobile}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost px-3 py-1.5 disabled:opacity-50"
              >
                {t("common:previous")}
              </button>
              <span className="text-sm text-[hsl(var(--text-secondary))]">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="btn-ghost px-3 py-1.5 disabled:opacity-50"
              >
                {t("common:next")}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// Discovery Skill Card Component
function DiscoverySkillCard({
  skill,
  onAdd,
  adding,
  isMobile,
}: {
  skill: PublicSkill;
  onAdd: () => void;
  adding?: boolean;
  isMobile?: boolean;
}) {
  const { t } = useTranslation(["skills"]);
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`group relative bg-[hsl(var(--bg-secondary))] rounded-xl border border-[hsl(var(--border-color))] hover:border-[hsl(var(--accent-primary)/0.3)] hover:shadow-lg transition-all ${
        isMobile ? "p-3" : "p-4"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
              skill.source === "official"
                ? "bg-[hsl(var(--accent-primary)/0.1)]"
                : "bg-[hsl(var(--bg-tertiary))]"
            }`}
          >
            <Zap
              className={`w-5 h-5 ${
                skill.source === "official"
                  ? "text-[hsl(var(--accent-primary))]"
                  : "text-[hsl(var(--text-secondary))]"
              }`}
            />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-[hsl(var(--text-primary))] truncate text-sm">
              {skill.name}
            </h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              {skill.source === "official" ? (
                <span className="flex items-center gap-1 text-xs text-[hsl(var(--accent-primary))]">
                  <Shield className="w-3 h-3" />
                  {t("skills:official")}
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs text-[hsl(var(--text-tertiary))]">
                  <Users className="w-3 h-3" />
                  {skill.author_name || t("skills:community")}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Description */}
      {skill.description && (
        <p className="text-sm text-[hsl(var(--text-secondary))] mb-3 line-clamp-2">
          {skill.description}
        </p>
      )}

      {/* Triggers Preview */}
      {skill.tags && skill.tags.length > 0 && (
        <div className="mb-3">
          <div className="flex flex-wrap gap-1">
            {skill.tags.slice(0, 3).map((tag, idx) => (
              <span
                key={idx}
                className="px-1.5 py-0.5 text-xs bg-[hsl(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))] rounded font-mono"
              >
                {tag}
              </span>
            ))}
            {skill.tags.length > 3 && (
              <span className="text-xs text-[hsl(var(--text-tertiary))]">
                +{skill.tags.length - 3}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Category & Stats */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs px-2 py-0.5 rounded-full bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-secondary))]">
          {skill.category}
        </span>
        <span className="text-xs text-[hsl(var(--text-tertiary))]">
          {skill.add_count} {t("skills:addCount")}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {skill.is_added ? (
          <button
            disabled
            className="btn-ghost flex-1 h-9 flex items-center justify-center gap-1.5 text-sm opacity-60"
          >
            <Check className="w-4 h-4" />
            {t("skills:alreadyAdded")}
          </button>
        ) : (
          <button
            onClick={onAdd}
            disabled={adding}
            className="btn-primary flex-1 h-9 flex items-center justify-center gap-1.5 text-sm"
          >
            {adding ? (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            {t("skills:addToMine")}
          </button>
        )}
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-2 rounded-lg text-[hsl(var(--text-secondary))] hover:bg-[hsl(var(--bg-tertiary))] transition-colors"
          title={expanded ? t("skills:collapse") : t("skills:expand")}
        >
          {expanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Expanded Instructions */}
      {expanded && skill.instructions && (
        <div className="mt-3 pt-3 border-t border-[hsl(var(--border-color))]">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-xs font-medium text-[hsl(var(--text-tertiary))]">
              {t("skills:form.instructions")}
            </span>
          </div>
          <div
            className={`markdown-content bg-[hsl(var(--bg-tertiary))] rounded-xl ${
              isMobile ? "p-3 text-xs" : "p-4 text-sm"
            } max-h-48 overflow-y-auto`}
          >
            <LazyMarkdown>{skill.instructions}</LazyMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
