'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { MANA_THEMES, ManaTheme, DEFAULT_THEME } from '@/config/theme.config';

interface ThemeColors {
  accent: string;
  glow: string;
  muted: string;
  name: string;
  hex: string;
}

interface ThemeContextType {
  theme: ManaTheme;
  setTheme: (theme: ManaTheme) => void;
  colors: ThemeColors;
  themes: readonly ManaTheme[];
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_KEYS = Object.keys(MANA_THEMES) as ManaTheme[];

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ManaTheme>(DEFAULT_THEME);

  useEffect(() => {
    const stored = localStorage.getItem('mana-theme') as ManaTheme | null;
    if (stored && MANA_THEMES[stored]) {
      setThemeState(stored);
    }
  }, []);

  useEffect(() => {
    const colors = MANA_THEMES[theme];
    document.documentElement.style.setProperty('--accent', colors.accent);
    document.documentElement.style.setProperty('--accent-glow', colors.glow);
    document.documentElement.style.setProperty('--accent-muted', colors.muted);
    localStorage.setItem('mana-theme', theme);
  }, [theme]);

  const setTheme = (newTheme: ManaTheme) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        setTheme,
        colors: MANA_THEMES[theme],
        themes: THEME_KEYS,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

// Re-export types for convenience
export type { ManaTheme };
