import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MaterialViewer } from '../MaterialViewer'

let isMobile = false

vi.mock('../../../hooks/useMediaQuery', () => ({
  useIsMobile: () => isMobile,
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      (
        {
          'detail.emptyDescription': 'Select a material to preview',
          'detail.chapters': 'Chapters',
          'detail.characters': 'Characters',
          'detail.plots': 'Plots',
          'detail.storylines': 'Storylines',
          'detail.worldview': 'Worldview',
          'detail.cheat': 'Cheat',
          'detail.goldenfingers': 'Goldfingers',
          title: 'Material',
          'detail.chapter': `Chapter ${options?.number ?? ''}`,
          'detail.summary': 'Summary',
          'detail.chapterLabel': 'Chapter content',
          'detail.aliases': 'Aliases',
          'detail.description': 'Description',
          'detail.traits': 'Traits',
          'detail.relationships': 'Relationships',
          'detail.plotType': 'Plot type',
          'detail.relatedChapters': 'Related chapters',
          'detail.powerSystem': 'Power system',
          'detail.worldStructure': 'World structure',
          'detail.keyFactions': 'Key factions',
          'detail.goldenfingerType': 'Goldfinger type',
          'detail.evolutionHistory': 'Evolution history',
          'detail.noData': 'Metadata',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

describe('MaterialViewer', () => {
  beforeEach(() => {
    isMobile = false
  })

  it('renders the empty state when no node is selected', () => {
    render(<MaterialViewer node={null} />)
    expect(screen.getByText('Select a material to preview')).toBeInTheDocument()
  })

  it('renders chapter and character nodes with their specialized sections', () => {
    const { rerender } = render(
      <MaterialViewer
        node={{
          id: 'chapter-1',
          type: 'chapter',
          title: 'Battle Setup',
          content: 'Chapter body',
          metadata: {
            chapter_number: 12,
            summary: 'Summary text',
            plot_points: ['Point 1', 'Point 2'],
          },
          children: [{ id: 'child-1', type: 'chapter', title: 'Child chapter' }],
        } as never}
      />,
    )

    expect(screen.getByText('Battle Setup')).toBeInTheDocument()
    expect(screen.getByText('Chapter 12')).toBeInTheDocument()
    expect(screen.getByText('Summary text')).toBeInTheDocument()
    expect(screen.getByText('Point 1')).toBeInTheDocument()
    expect(screen.getByText('Child chapter')).toBeInTheDocument()

    rerender(
      <MaterialViewer
        node={{
          id: 'character-1',
          type: 'character',
          title: 'Hero',
          content: 'Character background',
          metadata: {
            name: 'Li Wei',
            alias: ['The Blade', 'Champion'],
            archetype: 'Reluctant hero',
            description: 'A determined fighter',
            traits: ['Brave', 'Calm'],
            relationships: { Mentor: 'Trusted guide' },
          },
        } as never}
      />,
    )

    expect(screen.getByText('Li Wei')).toBeInTheDocument()
    expect(screen.getByText('The Blade、Champion')).toBeInTheDocument()
    expect(screen.getByText('Brave')).toBeInTheDocument()
    expect(screen.getByText('Trusted guide')).toBeInTheDocument()
  })

  it('renders plot, world, cheat, and default nodes', () => {
    const { rerender, container } = render(
      <MaterialViewer
        node={{
          id: 'plot-1',
          type: 'plot',
          title: 'Betrayal arc',
          content: 'Plot details',
          metadata: {
            plot_type: 'Twist',
            description: 'An unexpected betrayal',
            related_chapters: [3, 7],
          },
          children: [{ id: 'plot-child', type: 'plot', title: 'Subplot' }],
        } as never}
      />,
    )

    expect(screen.getByText('Twist')).toBeInTheDocument()
    expect(screen.getByText('Chapter 3')).toBeInTheDocument()
    expect(screen.getByText('Subplot')).toBeInTheDocument()

    rerender(
      <MaterialViewer
        node={{
          id: 'world-1',
          type: 'world',
          title: 'Empire',
          content: 'World details',
          metadata: {
            power_system: 'Qi cultivation',
            world_structure: 'Three realms',
            key_forces: ['Royal court', 'Rebels'],
          },
        } as never}
      />,
    )

    expect(screen.getByText('Qi cultivation')).toBeInTheDocument()
    expect(screen.getByText('Royal court')).toBeInTheDocument()

    rerender(
      <MaterialViewer
        node={{
          id: 'cheat-1',
          type: 'goldfinger',
          title: 'Ancient relic',
          content: 'Relic details',
          metadata: {
            name: 'Phoenix Core',
            type: 'Artifact',
            description: 'Stores ancient power',
            evolution: ['Dormant', 'Awakened'],
          },
        } as never}
      />,
    )

    expect(screen.getByText('Phoenix Core')).toBeInTheDocument()
    expect(screen.getByText('Awakened')).toBeInTheDocument()

    rerender(
      <MaterialViewer
        node={{
          id: 'misc-1',
          type: 'material',
          title: 'Misc node',
          content: 'Misc body',
          metadata: { tone: 'grim', nested: { key: 'value' } },
          children: [{ id: 'misc-child', type: 'material', title: 'Misc child' }],
        } as never}
      />,
    )

    expect(screen.getByText('Metadata')).toBeInTheDocument()
    expect(screen.getByText('grim')).toBeInTheDocument()
    expect(container.textContent).toContain('"key": "value"')
    expect(screen.getByText('Misc child')).toBeInTheDocument()
  })

  it('uses mobile spacing variants for info cards', () => {
    isMobile = true
    render(
      <MaterialViewer
        node={{
          id: 'character-2',
          type: 'character',
          title: 'Scout',
          metadata: {
            name: 'Scout',
            archetype: 'Rogue',
          },
        } as never}
      />,
    )

    expect(screen.getAllByText('Scout').length).toBeGreaterThan(0)
    expect(screen.getByText('Rogue')).toBeInTheDocument()
  })
})
