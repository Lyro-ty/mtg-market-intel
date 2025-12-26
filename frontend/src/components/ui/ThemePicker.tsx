'use client';

import { useTheme, ManaTheme } from '@/contexts/ThemeContext';

const MANA_ORBS: { theme: ManaTheme; label: string; bgClass: string }[] = [
  { theme: 'white', label: 'White', bgClass: 'bg-[#F8F6D8]' },
  { theme: 'blue', label: 'Blue', bgClass: 'bg-[#0E68AB]' },
  { theme: 'black', label: 'Black', bgClass: 'bg-[#8B5CF6]' },
  { theme: 'red', label: 'Red', bgClass: 'bg-[#DC2626]' },
  { theme: 'green', label: 'Green', bgClass: 'bg-[#16A34A]' },
];

export function ThemePicker() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="flex items-center gap-4" role="radiogroup" aria-label="Select mana theme">
      {MANA_ORBS.map((orb) => (
        <button
          key={orb.theme}
          onClick={() => setTheme(orb.theme)}
          className={`
            relative w-12 h-12 rounded-full transition-all duration-300
            ${orb.bgClass}
            ${theme === orb.theme
              ? 'ring-2 ring-offset-2 ring-offset-[#0C0C10] ring-[rgb(var(--accent-glow))] scale-110'
              : 'hover:scale-105 opacity-80 hover:opacity-100'}
          `}
          role="radio"
          aria-checked={theme === orb.theme}
          aria-label={`${orb.label} theme`}
        >
          {theme === orb.theme && (
            <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-6 h-0.5 bg-[rgb(var(--accent))]" />
          )}
        </button>
      ))}
    </div>
  );
}
