import { render, screen } from '@testing-library/react'

vi.mock('../../contexts/ProjectContext', () => ({
  ProjectProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="project-provider">{children}</div>
  ),
}))

vi.mock('../../contexts/MaterialLibraryContext', () => ({
  MaterialLibraryProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="material-library-provider">{children}</div>
  ),
}))

vi.mock('../../contexts/MaterialAttachmentContext', () => ({
  MaterialAttachmentProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="material-attachment-provider">{children}</div>
  ),
}))

vi.mock('../../contexts/TextQuoteContext', () => ({
  TextQuoteProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="text-quote-provider">{children}</div>
  ),
}))

vi.mock('../../contexts/SkillTriggerContext', () => ({
  SkillTriggerProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="skill-trigger-provider">{children}</div>
  ),
}))

import { ProtectedProviders } from '../ProtectedProviders'

describe('ProtectedProviders', () => {
  it('composes all protected-route providers in the expected order', () => {
    render(
      <ProtectedProviders>
        <div data-testid="protected-child">child</div>
      </ProtectedProviders>,
    )

    const project = screen.getByTestId('project-provider')
    const materialLibrary = screen.getByTestId('material-library-provider')
    const materialAttachment = screen.getByTestId('material-attachment-provider')
    const textQuote = screen.getByTestId('text-quote-provider')
    const skillTrigger = screen.getByTestId('skill-trigger-provider')
    const child = screen.getByTestId('protected-child')

    expect(project).toContainElement(materialLibrary)
    expect(materialLibrary).toContainElement(materialAttachment)
    expect(materialAttachment).toContainElement(textQuote)
    expect(textQuote).toContainElement(skillTrigger)
    expect(skillTrigger).toContainElement(child)
  })
})
