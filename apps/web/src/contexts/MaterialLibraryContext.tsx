/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext } from 'react';
import { useMaterialLibrary, type MaterialLibraryState } from '../hooks/useMaterialLibrary';

const MaterialLibraryContext = createContext<MaterialLibraryState | null>(null);

export const MaterialLibraryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const state = useMaterialLibrary();
  return (
    <MaterialLibraryContext.Provider value={state}>
      {children}
    </MaterialLibraryContext.Provider>
  );
};

export function useMaterialLibraryContext(): MaterialLibraryState {
  const ctx = useContext(MaterialLibraryContext);
  if (!ctx) {
    throw new Error('useMaterialLibraryContext must be used within MaterialLibraryProvider');
  }
  return ctx;
}
