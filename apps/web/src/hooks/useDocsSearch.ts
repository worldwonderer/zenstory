import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { docsNavigation, flattenDocs, type DocNavItem } from '../data/docsNavigation';

export interface DocsSearchResult {
  title: string;
  titleZh: string;
  path: string;
  parentTitle?: string;
  parentTitleZh?: string;
  score: number;
}

export interface UseDocsSearchOptions {
  query: string;
  debounceMs?: number;
  maxResults?: number;
}

export interface UseDocsSearchReturn {
  results: DocsSearchResult[];
  isSearching: boolean;
  clearSearch: () => void;
}

/**
 * Calculate match score for sorting results
 * Bilingual support: searches both title and titleZh
 */
function getMatchScore(title: string, titleZh: string, query: string): number {
  const lowerQuery = query.toLowerCase();

  // Exact match on either language
  if (title.toLowerCase() === lowerQuery || titleZh === query) {
    return 4;
  }
  // Prefix match
  if (title.toLowerCase().startsWith(lowerQuery) || titleZh.startsWith(query)) {
    return 3;
  }
  // Contains match
  if (title.toLowerCase().includes(lowerQuery) || titleZh.includes(query)) {
    return 2;
  }
  // Fuzzy match (any character sequence)
  const fuzzyScore = (str: string) => {
    let index = 0;
    for (const char of lowerQuery) {
      index = str.toLowerCase().indexOf(char, index);
      if (index === -1) return 0;
      index++;
    }
    return 1;
  };
  return Math.max(fuzzyScore(title), fuzzyScore(titleZh));
}

/**
 * Build parent mapping for navigation items
 */
function buildParentMap(items: DocNavItem[], parent?: DocNavItem): Map<string, DocNavItem> {
  const map = new Map<string, DocNavItem>();
  for (const item of items) {
    if (parent) {
      map.set(item.path, parent);
    }
    if (item.children) {
      for (const child of item.children) {
        map.set(child.path, item);
      }
      const nested = buildParentMap(item.children, item);
      nested.forEach((value, key) => map.set(key, value));
    }
  }
  return map;
}

export function useDocsSearch({
  query,
  debounceMs = 300,
  maxResults = 20,
}: UseDocsSearchOptions): UseDocsSearchReturn {
  const { i18n } = useTranslation();
  const [results, setResults] = useState<DocsSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSearch = useCallback(() => {
    setResults([]);
    setIsSearching(false);
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
  }, []);

  const normalizedQuery = query.trim();

  useEffect(() => {
    if (!normalizedQuery) {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
      return;
    }

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect -- debounced local search state is intentionally effect-driven.
    setIsSearching(true);

    debounceRef.current = setTimeout(() => {
      const flatDocs = flattenDocs(docsNavigation);
      const parentMap = buildParentMap(docsNavigation);
      const searchResults: DocsSearchResult[] = [];

      for (const doc of flatDocs) {
        // Search only leaf docs to avoid category routes showing as results.
        if (doc.children && doc.children.length > 0) {
          continue;
        }
        const score = getMatchScore(doc.title, doc.titleZh, normalizedQuery);
        if (score > 0) {
          const parent = parentMap.get(doc.path);
          searchResults.push({
            title: doc.title,
            titleZh: doc.titleZh,
            path: doc.path,
            parentTitle: parent?.title,
            parentTitleZh: parent?.titleZh,
            score,
          });
        }
      }

      // Sort by score, then by current language preference
      const currentLang = i18n.language;
      searchResults.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        const aTitle = currentLang === 'zh' ? a.titleZh : a.title;
        const bTitle = currentLang === 'zh' ? b.titleZh : b.title;
        return aTitle.localeCompare(bTitle, currentLang === 'zh' ? 'zh-CN' : 'en');
      });

      setResults(searchResults.slice(0, maxResults));
      setIsSearching(false);
    }, debounceMs);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [normalizedQuery, debounceMs, maxResults, i18n.language]);

  return {
    results: normalizedQuery ? results : [],
    isSearching: normalizedQuery ? isSearching : false,
    clearSearch,
  };
}
