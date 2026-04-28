import { fireEvent, render, renderHook, screen } from '@testing-library/react'
import { FileSearchProvider, useFileSearchContext } from '../FileSearchContext'

function FileSearchConsumer() {
  const { isSearchOpen, openSearch, closeSearch, toggleSearch } = useFileSearchContext()

  return (
    <div>
      <div data-testid="search-open">{String(isSearchOpen)}</div>
      <button type="button" onClick={openSearch}>
        open
      </button>
      <button type="button" onClick={closeSearch}>
        close
      </button>
      <button type="button" onClick={toggleSearch}>
        toggle
      </button>
    </div>
  )
}

describe('FileSearchContext', () => {
  it('opens, closes, and toggles the search panel state', () => {
    render(
      <FileSearchProvider>
        <FileSearchConsumer />
      </FileSearchProvider>,
    )

    expect(screen.getByTestId('search-open')).toHaveTextContent('false')

    fireEvent.click(screen.getByRole('button', { name: 'open' }))
    expect(screen.getByTestId('search-open')).toHaveTextContent('true')

    fireEvent.click(screen.getByRole('button', { name: 'toggle' }))
    expect(screen.getByTestId('search-open')).toHaveTextContent('false')

    fireEvent.click(screen.getByRole('button', { name: 'close' }))
    expect(screen.getByTestId('search-open')).toHaveTextContent('false')
  })

  it('throws when used outside its provider', () => {
    expect(() => renderHook(() => useFileSearchContext())).toThrow(
      'useFileSearchContext must be used within FileSearchProvider',
    )
  })
})
