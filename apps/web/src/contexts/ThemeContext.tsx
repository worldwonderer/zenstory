import React, { createContext, useContext, useEffect, useState } from 'react';

type ThemeMode = 'dark' | 'light';

interface ThemeContextType {
  theme: ThemeMode;
  accentColor: string;
  setTheme: (theme: ThemeMode) => void;
  setAccentColor: (color: string) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// Default colors
const ACCENT_COLORS: Record<string, { primary: string; dark: string; light: string }> = {
  '#4a9eff': { primary: '217 91% 64%', dark: '217 91% 54%', light: '217 91% 74%' },
  '#22c55e': { primary: '142 71% 45%', dark: '142 71% 35%', light: '142 71% 55%' },
  '#fbbf24': { primary: '38 92% 50%', dark: '38 92% 40%', light: '38 92% 60%' },
  '#f87171': { primary: '0 84% 60%', dark: '0 84% 50%', light: '0 84% 70%' },
  '#ec4899': { primary: '330 81% 60%', dark: '330 81% 50%', light: '330 81% 70%' },
  '#8b5cf6': { primary: '262 83% 64%', dark: '262 83% 54%', light: '262 83% 74%' },
};

// Helper function to get initial theme from localStorage
function getInitialTheme(): ThemeMode {
  const saved = localStorage.getItem('zenstory-theme');
  if (saved === 'dark' || saved === 'light') {
    return saved;
  }
  return 'light';
}

function getInitialAccentColor(): string {
  const savedColor = localStorage.getItem('zenstory-accent-color');
  return savedColor && savedColor in ACCENT_COLORS ? savedColor : '#4a9eff';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(getInitialTheme);
  const [accentColor, setAccentColorState] = useState(getInitialAccentColor);

  // Apply theme to document and localStorage when changed
  useEffect(() => {
    // Apply theme class
    document.documentElement.classList.remove('dark', 'light');
    document.documentElement.classList.add(theme);
    localStorage.setItem('zenstory-theme', theme);

    // Apply theme-specific CSS variables
    if (theme === 'dark') {
      document.documentElement.style.setProperty('--bg-primary', '30 10% 11%');      /* #1e1e1e */
      document.documentElement.style.setProperty('--bg-secondary', '30 10% 16%');    /* #252526 */
      document.documentElement.style.setProperty('--bg-tertiary', '30 10% 20%');     /* #2d2d2d */
      document.documentElement.style.setProperty('--text-primary', '0 0% 88%');      /* #e0e0e0 */
      document.documentElement.style.setProperty('--text-secondary', '0 0% 53%');    /* #888888 */
      document.documentElement.style.setProperty('--border-color', '0 0% 24%');    /* #3d3d3d */
      document.documentElement.style.setProperty('--bg-card', '30 10% 18%');         /* #2e2e2e */
    } else {
      document.documentElement.style.setProperty('--bg-primary', '210 20% 98%');    /* #fafafa */
      document.documentElement.style.setProperty('--bg-secondary', '210 20% 96%');  /* #f5f5f5 */
      document.documentElement.style.setProperty('--bg-tertiary', '210 20% 94%');   /* #f0f0f0 */
      document.documentElement.style.setProperty('--text-primary', '210 15% 15%');  /* #262626 */
      document.documentElement.style.setProperty('--text-secondary', '210 15% 50%'); /* #808080 */
      document.documentElement.style.setProperty('--border-color', '210 15% 85%');  /* #d9d9d9 */
      document.documentElement.style.setProperty('--bg-card', '0 0% 100%');          /* #ffffff */
    }
  }, [theme]);

  // Apply accent color
  useEffect(() => {
    const colorData = ACCENT_COLORS[accentColor] || ACCENT_COLORS['#4a9eff'];

    document.documentElement.style.setProperty('--accent-primary', colorData.primary);
    document.documentElement.style.setProperty('--accent-dark', colorData.dark);
    document.documentElement.style.setProperty('--accent-light', colorData.light);
    localStorage.setItem('zenstory-accent-color', accentColor);
  }, [accentColor]);

  const setTheme = (newTheme: ThemeMode) => {
    setThemeState(newTheme);
  };

  const setAccentColor = (newColor: string) => {
    setAccentColorState(newColor);
  };

  return (
    <ThemeContext.Provider value={{ theme, accentColor, setTheme, setAccentColor }}>
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
