import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import {
  MAX_TEXT_QUOTES,
  TextQuoteProvider,
  useTextQuote,
} from '../TextQuoteContext'

function TextQuoteConsumer() {
  const { quotes, addQuote, removeQuote, clearQuotes, isAtLimit } = useTextQuote()

  return (
    <div>
      <div data-testid="quote-count">{quotes.length}</div>
      <div data-testid="quote-text">{quotes.map((quote) => quote.text).join(',')}</div>
      <div data-testid="quote-limit">{String(isAtLimit)}</div>
      <button type="button" onClick={() => addQuote('A quote', 'file-1', 'Draft one')}>
        add-quote
      </button>
      <button type="button" onClick={() => removeQuote('quote-1')}>
        remove-quote
      </button>
      <button type="button" onClick={clearQuotes}>
        clear-quotes
      </button>
    </div>
  )
}

describe('TextQuoteContext', () => {
  beforeEach(() => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('quote-1')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('adds, removes, and clears text quotes', () => {
    render(
      <TextQuoteProvider>
        <TextQuoteConsumer />
      </TextQuoteProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'add-quote' }))
    expect(screen.getByTestId('quote-count')).toHaveTextContent('1')
    expect(screen.getByTestId('quote-text')).toHaveTextContent('A quote')

    fireEvent.click(screen.getByRole('button', { name: 'remove-quote' }))
    expect(screen.getByTestId('quote-count')).toHaveTextContent('0')

    fireEvent.click(screen.getByRole('button', { name: 'add-quote' }))
    fireEvent.click(screen.getByRole('button', { name: 'clear-quotes' }))
    expect(screen.getByTestId('quote-count')).toHaveTextContent('0')
  })

  it('enforces the maximum quote limit', () => {
    const { result } = renderHook(() => useTextQuote(), {
      wrapper: ({ children }) => <TextQuoteProvider>{children}</TextQuoteProvider>,
    })

    for (let index = 0; index < MAX_TEXT_QUOTES; index += 1) {
      vi.mocked(crypto.randomUUID).mockReturnValue(`quote-${index + 1}`)
      act(() => {
        expect(result.current.addQuote(`Quote ${index + 1}`, `file-${index}`, 'Draft')).toBe(true)
      })
    }

    expect(result.current.isAtLimit).toBe(true)
    vi.mocked(crypto.randomUUID).mockReturnValue('quote-overflow')
    act(() => {
      expect(result.current.addQuote('Overflow', 'file-overflow', 'Draft')).toBe(false)
    })
  })

  it('throws when used outside its provider', () => {
    expect(() => renderHook(() => useTextQuote())).toThrow(
      'useTextQuote must be used within a TextQuoteProvider',
    )
  })
})
