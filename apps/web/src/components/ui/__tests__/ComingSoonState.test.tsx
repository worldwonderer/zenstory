import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ComingSoonState } from '../ComingSoonState'

describe('ComingSoonState', () => {
  it('renders the default state content', () => {
    render(<ComingSoonState title="Soon" description="Feature is on the way" />)

    expect(screen.getByTestId('coming-soon-state')).toBeInTheDocument()
    expect(screen.getByText('Soon')).toBeInTheDocument()
    expect(screen.getByText('Feature is on the way')).toBeInTheDocument()
  })

  it('renders the compact variant with custom classes', () => {
    render(
      <ComingSoonState
        title="Compact"
        description="Small state"
        compact={true}
        className="custom-state"
      />,
    )

    const state = screen.getByTestId('coming-soon-state')
    expect(state.className).toContain('px-4')
    expect(state.className).toContain('custom-state')
  })
})
