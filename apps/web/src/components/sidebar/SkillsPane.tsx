import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSkillTrigger } from "../../contexts/SkillTriggerContext";
import { skillsApi } from "../../lib/api";
import type { Skill } from "../../types";
import { LazyMarkdown } from "../LazyMarkdown";
import { logger } from "../../lib/logger";
import {
  Zap,
  Plus,
  X,
} from "lucide-react";

/**
 * SkillsPane - Skills browser component
 *
 * Sidebar pane for skills management.
 * Displays available skills with detail modal and trigger insertion.
 */
export const SkillsPane: React.FC = () => {
  const { t } = useTranslation(['editor', 'common']);
  const { insertTrigger } = useSkillTrigger();

  // Skills state
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(true);

  // Load skills
  useEffect(() => {
    const loadSkills = async () => {
      try {
        setLoading(true);
        const response = await skillsApi.list();
        setSkills((response.skills || []).filter((skill) => skill.is_active));
      } catch (error) {
        logger.error("Failed to load skills:", error);
      } finally {
        setLoading(false);
      }
    };
    loadSkills();
  }, []);

  // Handle skill click - show detail modal
  const handleSkillClick = useCallback((skill: Skill) => {
    setSelectedSkill(skill);
  }, []);

  // Handle close modal
  const handleCloseModal = useCallback(() => {
    setSelectedSkill(null);
  }, []);

  // Handle use skill - insert trigger
  const handleUseSkill = useCallback((e: React.MouseEvent, skill: Skill) => {
    e.stopPropagation();
    insertTrigger(skill.triggers[0] || skill.name);
  }, [insertTrigger]);

  return (
    <div className="w-full h-full text-sm overflow-auto p-2">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2 px-2">
        <Zap size={14} className="text-[hsl(var(--text-secondary))]" />
        <span className="text-sm font-medium text-[hsl(var(--text-primary))]">
          {t('editor:fileTree.skillsFolder')}
        </span>
        <span className="text-xs text-[hsl(var(--text-secondary))]">
          ({skills.length})
        </span>
      </div>

      {/* Skills list */}
      {loading ? (
        <div className="px-2 py-2 text-[hsl(var(--text-secondary))] text-xs italic">
          {t('common:loading')}
        </div>
      ) : skills.length === 0 ? (
        <div className="px-2 py-2 text-[hsl(var(--text-secondary))] text-xs italic">
          {t('editor:fileTree.skillsEmpty')}
        </div>
      ) : (
        <div className="mt-0.5">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer group transition-colors text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))]"
              onClick={() => handleSkillClick(skill)}
            >
              <span className="w-3.5" />
              <span className="text-[hsl(var(--text-secondary))]">
                <Zap size={14} />
              </span>
              <span className="flex-1 truncate">{skill.name}</span>
              <button
                onClick={(e) => handleUseSkill(e, skill)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[hsl(var(--accent-primary)/0.15)] text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--accent-primary))] transition-all"
                title={t('editor:fileTree.useSkill')}
              >
                <Plus size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Skill detail modal */}
      {selectedSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-white/10" onClick={handleCloseModal}>
          <div
            className="bg-[hsl(var(--bg-secondary))] rounded-lg shadow-xl max-w-md w-full mx-4 max-h-[80vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[hsl(var(--border-primary))]">
              <div className="flex items-center gap-2">
                <Zap size={18} className="text-[hsl(var(--accent-primary))]" />
                <h3 className="font-medium text-[hsl(var(--text-primary))]">{selectedSkill.name}</h3>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  selectedSkill.source === 'builtin'
                    ? 'bg-[hsl(var(--accent-primary)/0.1)] text-[hsl(var(--accent-primary))]'
                    : 'bg-[hsl(var(--success)/0.1)] text-[hsl(var(--success))]'
                }`}>
                  {selectedSkill.source === 'builtin' ? t('editor:fileTree.builtinSkill') : t('editor:fileTree.userSkill')}
                </span>
              </div>
              <button
                onClick={handleCloseModal}
                className="p-1 text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal content */}
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {/* Description */}
              {selectedSkill.description && (
                <p className="text-sm text-[hsl(var(--text-secondary))] mb-4">
                  {selectedSkill.description}
                </p>
              )}

              {/* Triggers */}
              <div className="mb-4">
                <h4 className="text-xs font-medium text-[hsl(var(--text-secondary))] uppercase mb-2">
                  {t('editor:fileTree.skillTriggers')}
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedSkill.triggers.map((trigger, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 text-xs bg-[hsl(var(--bg-tertiary))] text-[hsl(var(--text-primary))] rounded"
                    >
                      {trigger}
                    </span>
                  ))}
                </div>
              </div>

              {/* Instructions */}
              <div>
                <h4 className="text-xs font-medium text-[hsl(var(--text-secondary))] uppercase mb-2">
                  {t('editor:fileTree.skillInstructions')}
                </h4>
                <div className="markdown-content p-3 bg-[hsl(var(--bg-tertiary))] rounded text-sm text-[hsl(var(--text-primary))] max-h-48 overflow-y-auto">
                  <LazyMarkdown>
                    {selectedSkill.instructions}
                  </LazyMarkdown>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
