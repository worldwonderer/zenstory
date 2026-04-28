import { render, screen } from '@testing-library/react'
import { CommonProviders } from '../CommonProviders'

describe('CommonProviders', () => {
  it('renders children without adding extra wrappers', () => {
    render(
      <CommonProviders>
        <div data-testid="common-child">content</div>
      </CommonProviders>,
    )

    expect(screen.getByTestId('common-child')).toHaveTextContent('content')
  })
})
