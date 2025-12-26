'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

export type ManaTheme = 'white' | 'blue' | 'black' | 'red' | 'green';

interface ThemeColors {
  primary: string;
  glow: string;
  muted: string;
}

const THEME_COLORS: Record<ManaTheme, ThemeColors> = {
  white: { primary: '248 246 216', glow: '255 254 245', muted: '201 198 165' },
  blue: { primary: '14 104 171', glow: '30 144 255', muted: '10 74 122' },
  black: { primary: '139 92 246', glow: '167 139 250', muted: '109 40 217' },
  red: { primary: '220 38 38', glow: '239 68 68', muted: '153 27 27' },
  green: { primary: '22 163 74', glow: '34 197 94', muted: '21 128 61' },
};

interface ThemeContextType {
  theme: ManaTheme;
  setTheme: (theme: ManaTheme) => void;
  colors: ThemeColors;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ManaTheme>('blue');

  useEffect(() => {
    const stored = localStorage.getItem('mana-theme') as ManaTheme | null;
    if (stored && THEME_COLORS[stored]) {
      setThemeState(stored);
    }
  }, []);

  useEffect(() => {
    const colors = THEME_COLORS[theme];
    document.documentElement.style.setProperty('--accent', colors.primary);
    document.documentElement.style.setProperty('--accent-glow', colors.glow);
    document.documentElement.style.setProperty('--accent-muted', colors.muted);
    localStorage.setItem('mana-theme', theme);
  }, [theme]);

  const setTheme = (newTheme: ManaTheme) => {
    setThemeState(newTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, colors: THEME_COLORS[theme] }}>
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
