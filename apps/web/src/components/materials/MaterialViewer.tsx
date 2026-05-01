import React from 'react';
import type { MaterialTreeNode } from '../../types';
import { useIsMobile } from '../../hooks/useMediaQuery';
import { useTranslation } from 'react-i18next';
import i18n from '../../lib/i18n';

interface MaterialViewerProps {
  node: MaterialTreeNode | null;
}

/**
 * MaterialViewer - Renders different content based on material node type
 *
 * Supports:
 * - chapter: Summary + plot points list
 * - character: Basic info (name, alias, description, archetype)
 * - plot/story/storyline: Description + related chapters
 * - world: Power system, world structure, key forces
 * - cheat/goldfinger: Name, type, description, evolution history
 */
export const MaterialViewer = ({ node }: MaterialViewerProps) => {
  const isMobile = useIsMobile();
  const { t } = useTranslation('materials');

  if (!node) {
    return (
      <div className="flex items-center justify-center h-full text-[hsl(var(--text-secondary))]">
        <p>{t('detail.emptyDescription')}</p>
      </div>
    );
  }

  return (
    <div className={`h-full overflow-y-auto bg-[hsl(var(--bg-primary))] ${isMobile ? 'p-4' : 'p-6'}`}>
      <div className={isMobile ? '' : 'max-w-4xl mx-auto'}>
        {/* Header */}
        <div className="mb-6 pb-4 border-b border-[hsl(var(--border-color))]">
          <div className="flex items-center gap-3 mb-2">
            <TypeBadge type={node.type} />
            <h1 className={`font-bold text-[hsl(var(--text-primary))] ${isMobile ? 'text-xl' : 'text-2xl'}`}>
              {node.title}
            </h1>
          </div>
          {node.id && (
            <p className="text-sm text-[hsl(var(--text-secondary))]">
              {t('detail.idLabel')}: {node.id}
            </p>
          )}
        </div>

        {/* Content based on type */}
        {renderContent(node, t)}
      </div>
    </div>
  );
};

/**
 * Type badge component
 */
const TypeBadge = ({ type }: { type: string }) => {
  const { t } = useTranslation('materials');
  const config = getTypeConfig(type, t);

  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${config.className}`}
    >
      {config.label}
    </span>
  );
};

/**
 * Get type configuration for styling and labels
 */
function getTypeConfig(type: string, t: (key: string) => string) {
  const configs: Record<string, { label: string; className: string }> = {
    chapter: {
      label: t('detail.chapters'),
      className: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    },
    character: {
      label: t('detail.characters'),
      className: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    },
    plot: {
      label: t('detail.plots'),
      className: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    },
    story: {
      label: t('detail.storylines'),
      className: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
    },
    storyline: {
      label: t('detail.storylines'),
      className: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
    },
    world: {
      label: t('detail.worldview'),
      className: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    },
    cheat: {
      label: t('detail.cheat'),
      className: 'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200',
    },
    goldfinger: {
      label: t('detail.goldenfingers'),
      className: 'bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200',
    },
    material: {
      label: t('title'),
      className: 'bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-primary))]',
    },
  };

  return configs[type] || configs.material;
}

/**
 * Render content based on node type
 */
function renderContent(node: MaterialTreeNode, t: (key: string) => string): React.ReactElement {
  switch (node.type) {
    case 'chapter':
      return <ChapterContent node={node} t={t} />;
    case 'character':
      return <CharacterContent node={node} t={t} />;
    case 'plot':
    case 'story':
    case 'storyline':
      return <PlotContent node={node} t={t} />;
    case 'world':
      return <WorldContent node={node} t={t} />;
    case 'cheat':
    case 'goldfinger':
      return <CheatContent node={node} t={t} />;
    default:
      return <DefaultContent node={node} t={t} />;
  }
}

/**
 * Chapter content renderer
 */
const ChapterContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string, options?: Record<string, unknown>) => string }) => {
  const metadata = node.metadata || {};
  const summary = metadata.summary as string | undefined;
  const plotPoints = metadata.plot_points as string[] | undefined;
  const chapterNumber = metadata.chapter_number as number | undefined;

  return (
    <div className="space-y-6">
      {/* Chapter number */}
      {chapterNumber !== undefined && (
        <div className="text-sm text-[hsl(var(--text-secondary))]">
          {t('detail.chapter', { number: chapterNumber })}
        </div>
      )}

      {/* Summary */}
      {summary && (
        <Section title={t('detail.summary')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {summary}
          </p>
        </Section>
      )}

      {/* Plot points */}
      {plotPoints && plotPoints.length > 0 && (
        <Section title={t('detail.plots')}>
          <ul className="space-y-2">
            {plotPoints.map((point, index) => (
              <li
                key={index}
                className="flex items-start gap-3 text-[hsl(var(--text-primary))]"
              >
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs font-medium">
                  {index + 1}
                </span>
                <span className="flex-1">{point}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Content */}
      {node.content && (
        <Section title={t('detail.chapterLabel')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}

      {/* Children chapters */}
      {node.children && node.children.length > 0 && (
        <Section title={t('detail.chapters')}>
          <div className="grid gap-2">
            {node.children.map((child) => (
              <div
                key={child.id}
                className="p-3 rounded-lg border border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-secondary))] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <TypeBadge type={child.type} />
                  <span className="text-sm font-medium text-[hsl(var(--text-primary))]">
                    {child.title}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * Character content renderer
 */
const CharacterContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string) => string }) => {
  const isMobile = useIsMobile();
  const metadata = node.metadata || {};
  const name = metadata.name as string | undefined;
  const alias = metadata.alias as string | string[] | undefined;
  const description = metadata.description as string | undefined;
  const archetype = metadata.archetype as string | undefined;
  const traits = metadata.traits as string[] | undefined;
  const relationships = metadata.relationships as Record<string, string> | undefined;

  return (
    <div className="space-y-6">
      {/* Basic info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {name && (
          <InfoCard label={t('detail.summary')} value={name} isMobile={isMobile} />
        )}
        {alias && (
          <InfoCard
            label={t('detail.aliases')}
            value={Array.isArray(alias) ? alias.join(i18n.language === 'zh' ? '、' : ', ') : alias}
            isMobile={isMobile}
          />
        )}
        {archetype && (
          <InfoCard label={t('detail.plotType')} value={archetype} isMobile={isMobile} />
        )}
      </div>

      {/* Description */}
      {description && (
        <Section title={t('detail.description')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {description}
          </p>
        </Section>
      )}

      {/* Traits */}
      {traits && traits.length > 0 && (
        <Section title={t('detail.traits')}>
          <div className="flex flex-wrap gap-2">
            {traits.map((trait, index) => (
              <span
                key={index}
                className="px-3 py-1 rounded-full text-sm bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200"
              >
                {trait}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Relationships */}
      {relationships && Object.keys(relationships).length > 0 && (
        <Section title={t('detail.relationships')}>
          <div className="space-y-2">
            {Object.entries(relationships).map(([character, relation]) => (
              <div
                key={character}
                className="flex items-center gap-3 p-3 rounded-lg bg-[hsl(var(--bg-secondary))]"
              >
                <span className="font-medium text-[hsl(var(--text-primary))]">
                  {character}
                </span>
                <span className="text-[hsl(var(--text-secondary))]">·</span>
                <span className="text-[hsl(var(--text-primary))]">
                  {relation}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Content */}
      {node.content && (
        <Section title={t('detail.description')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * Plot/Story content renderer
 */
const PlotContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string, options?: Record<string, unknown>) => string }) => {
  const isMobile = useIsMobile();
  const metadata = node.metadata || {};
  const description = metadata.description as string | undefined;
  const relatedChapters = metadata.related_chapters as number[] | undefined;
  const plotType = metadata.plot_type as string | undefined;

  return (
    <div className="space-y-6">
      {/* Plot type */}
      {plotType && (
        <InfoCard label={t('detail.plotType')} value={plotType} isMobile={isMobile} />
      )}

      {/* Description */}
      {description && (
        <Section title={t('detail.description')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {description}
          </p>
        </Section>
      )}

      {/* Related chapters */}
      {relatedChapters && relatedChapters.length > 0 && (
        <Section title={t('detail.relatedChapters')}>
          <div className="flex flex-wrap gap-2">
            {relatedChapters.map((chapterNum) => (
              <span
                key={chapterNum}
                className="px-3 py-1 rounded-lg text-sm bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 font-medium"
              >
                {t('detail.chapter', { number: chapterNum })}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Content */}
      {node.content && (
        <Section title={t('detail.description')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}

      {/* Children */}
      {node.children && node.children.length > 0 && (
        <Section title={t('detail.plots')}>
          <div className="grid gap-2">
            {node.children.map((child) => (
              <div
                key={child.id}
                className="p-3 rounded-lg border border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-secondary))] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <TypeBadge type={child.type} />
                  <span className="text-sm font-medium text-[hsl(var(--text-primary))]">
                    {child.title}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * World content renderer
 */
const WorldContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string) => string }) => {
  const metadata = node.metadata || {};
  const powerSystem = metadata.power_system as string | undefined;
  const worldStructure = metadata.world_structure as string | undefined;
  const keyForces = metadata.key_forces as string[] | undefined;

  return (
    <div className="space-y-6">
      {/* Power system */}
      {powerSystem && (
        <Section title={t('detail.powerSystem')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {powerSystem}
          </p>
        </Section>
      )}

      {/* World structure */}
      {worldStructure && (
        <Section title={t('detail.worldStructure')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {worldStructure}
          </p>
        </Section>
      )}

      {/* Key forces */}
      {keyForces && keyForces.length > 0 && (
        <Section title={t('detail.keyFactions')}>
          <div className="space-y-3">
            {keyForces.map((force, index) => (
              <div
                key={index}
                className="p-4 rounded-lg bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800"
              >
                <p className="text-[hsl(var(--text-primary))]">{force}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Content */}
      {node.content && (
        <Section title={t('detail.description')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * Cheat/Goldfinger content renderer
 */
const CheatContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string) => string }) => {
  const isMobile = useIsMobile();
  const metadata = node.metadata || {};
  const cheatName = metadata.name as string | undefined;
  const cheatType = metadata.type as string | undefined;
  const description = metadata.description as string | undefined;
  const evolution = metadata.evolution as string[] | undefined;

  return (
    <div className="space-y-6">
      {/* Basic info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {cheatName && (
          <InfoCard label={t('title')} value={cheatName} isMobile={isMobile} />
        )}
        {cheatType && (
          <InfoCard label={t('detail.goldenfingerType')} value={cheatType} isMobile={isMobile} />
        )}
      </div>

      {/* Description */}
      {description && (
        <Section title={t('detail.description')}>
          <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
            {description}
          </p>
        </Section>
      )}

      {/* Evolution history */}
      {evolution && evolution.length > 0 && (
        <Section title={t('detail.evolutionHistory')}>
          <div className="space-y-3">
            {evolution.map((stage, index) => (
              <div
                key={index}
                className="flex items-start gap-4 p-4 rounded-lg bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800"
              >
                <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-full bg-rose-500 text-white text-sm font-bold">
                  {index + 1}
                </div>
                <p className="flex-1 text-[hsl(var(--text-primary))]">{stage}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Content */}
      {node.content && (
        <Section title={t('detail.description')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * Default content renderer for unknown types
 */
const DefaultContent = ({ node, t }: { node: MaterialTreeNode; t: (key: string) => string }) => {
  return (
    <div className="space-y-6">
      {/* Content */}
      {node.content && (
        <Section title={t('detail.description')}>
          <div className="prose dark:prose-invert max-w-none">
            <p className="text-[hsl(var(--text-primary))] leading-relaxed whitespace-pre-wrap">
              {node.content}
            </p>
          </div>
        </Section>
      )}

      {/* Metadata */}
      {node.metadata && Object.keys(node.metadata).length > 0 && (
        <Section title={t('detail.noData')}>
          <div className="space-y-2">
            {Object.entries(node.metadata).map(([key, value]) => (
              <div
                key={key}
                className="flex items-start gap-3 p-3 rounded-lg bg-[hsl(var(--bg-secondary))]"
              >
                <span className="font-medium text-[hsl(var(--text-secondary))] min-w-[100px]">
                  {key}:
                </span>
                <span className="text-[hsl(var(--text-primary))]">
                  {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                </span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Children */}
      {node.children && node.children.length > 0 && (
        <Section title={t('detail.chapters')}>
          <div className="grid gap-2">
            {node.children.map((child) => (
              <div
                key={child.id}
                className="p-3 rounded-lg border border-[hsl(var(--border-color))] hover:bg-[hsl(var(--bg-secondary))] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <TypeBadge type={child.type} />
                  <span className="text-sm font-medium text-[hsl(var(--text-primary))]">
                    {child.title}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
};

/**
 * Section component for consistent section styling
 */
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => {
  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-[hsl(var(--text-primary))] border-b border-[hsl(var(--border-color))] pb-2">
        {title}
      </h2>
      <div>{children}</div>
    </div>
  );
};

/**
 * InfoCard component for displaying key-value pairs
 */
const InfoCard = ({ label, value, isMobile }: { label: string; value: string; isMobile?: boolean }) => {
  return (
    <div className={`rounded-lg bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-color))] ${isMobile ? 'p-3' : 'p-4'}`}>
      <div className="text-sm text-[hsl(var(--text-secondary))] mb-1">{label}</div>
      <div className="text-base font-medium text-[hsl(var(--text-primary))]">{value}</div>
    </div>
  );
};
