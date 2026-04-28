import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import type { TextQuote } from '../types';

/**
 * Maximum number of text quotes that can be added at once
 */
export const MAX_TEXT_QUOTES = 5;

export interface TextQuoteContextType {
  /** List of quoted text items */
  quotes: TextQuote[];
  /** Add a text quote */
  addQuote: (text: string, fileId: string, fileTitle: string) => boolean;
  /** Remove a text quote by id */
  removeQuote: (id: string) => void;
  /** Clear all text quotes */
  clearQuotes: () => void;
  /** Whether the maximum limit is reached */
  isAtLimit: boolean;
}

const TextQuoteContext = createContext<TextQuoteContextType | undefined>(undefined);

export const TextQuoteProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [quotes, setQuotes] = useState<TextQuote[]>([]);
  const quotesRef = useRef<TextQuote[]>(quotes);

  useEffect(() => {
    quotesRef.current = quotes;
  }, [quotes]);

  // Check if at limit
  const isAtLimit = quotes.length >= MAX_TEXT_QUOTES;

  // Add a quote
  const addQuote = useCallback((text: string, fileId: string, fileTitle: string): boolean => {
    const current = quotesRef.current;

    // Check limit
    if (current.length >= MAX_TEXT_QUOTES) {
      return false;
    }

    const newQuote: TextQuote = {
      id: crypto.randomUUID(),
      text,
      fileId,
      fileTitle,
      createdAt: new Date(),
    };

    const next = [...current, newQuote];
    quotesRef.current = next;
    setQuotes(next);
    return true;
  }, []);

  // Remove a quote
  const removeQuote = useCallback((id: string) => {
    setQuotes(prev => {
      const next = prev.filter(q => q.id !== id);
      quotesRef.current = next;
      return next;
    });
  }, []);

  // Clear all quotes
  const clearQuotes = useCallback(() => {
    quotesRef.current = [];
    setQuotes([]);
  }, []);

  const value: TextQuoteContextType = {
    quotes,
    addQuote,
    removeQuote,
    clearQuotes,
    isAtLimit,
  };

  return (
    <TextQuoteContext.Provider value={value}>
      {children}
    </TextQuoteContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useTextQuote = (): TextQuoteContextType => {
  const context = useContext(TextQuoteContext);
  if (context === undefined) {
    throw new Error('useTextQuote must be used within a TextQuoteProvider');
  }
  return context;
};
