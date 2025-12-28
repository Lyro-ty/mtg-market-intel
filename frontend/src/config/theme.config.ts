// Mana theme configuration for MTG-inspired color schemes
// Each theme corresponds to one of Magic: The Gathering's five mana colors

export const MANA_THEMES = {
  white: {
    accent: '248 246 216',
    glow: '255 254 245',
    muted: '201 198 165',
    name: 'Plains',
    hex: '#F8F6D8',
  },
  blue: {
    accent: '14 104 171',
    glow: '30 144 255',
    muted: '10 74 122',
    name: 'Island',
    hex: '#0E68AB',
  },
  black: {
    accent: '139 92 246',
    glow: '167 139 250',
    muted: '109 40 217',
    name: 'Swamp',
    hex: '#8B5CF6',
  },
  red: {
    accent: '220 38 38',
    glow: '239 68 68',
    muted: '153 27 27',
    name: 'Mountain',
    hex: '#DC2626',
  },
  green: {
    accent: '22 163 74',
    glow: '34 197 94',
    muted: '21 128 61',
    name: 'Forest',
    hex: '#16A34A',
  },
} as const;

export type ManaTheme = keyof typeof MANA_THEMES;

export const DEFAULT_THEME: ManaTheme = 'blue';
