/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface FileSearchContextType {
  isSearchOpen: boolean;
  openSearch: () => void;
  closeSearch: () => void;
  toggleSearch: () => void;
}

const FileSearchContext = createContext<FileSearchContextType | undefined>(undefined);

export const FileSearchProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const openSearch = useCallback(() => setIsSearchOpen(true), []);
  const closeSearch = useCallback(() => setIsSearchOpen(false), []);
  const toggleSearch = useCallback(() => setIsSearchOpen(prev => !prev), []);

  return (
    <FileSearchContext.Provider value={{ isSearchOpen, openSearch, closeSearch, toggleSearch }}>
      {children}
    </FileSearchContext.Provider>
  );
};

export const useFileSearchContext = () => {
  const context = useContext(FileSearchContext);
  if (!context) {
    throw new Error('useFileSearchContext must be used within FileSearchProvider');
  }
  return context;
};
