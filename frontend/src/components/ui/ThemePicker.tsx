'use client';

import { useTheme, ManaTheme } from '@/contexts/ThemeContext';
import { cn } from '@/lib/utils';

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
    <div className="flex flex-col gap-3">
      <span className="text-sm font-medium text-[rgb(var(--foreground))]">
        Mana Theme
      </span>
      <div className="flex gap-4">
        {MANA_ORBS.map((orb) => (
          <button
            key={orb.theme}
            onClick={() => setTheme(orb.theme)}
            className={cn(
              'flex flex-col items-center gap-2 group'
            )}
            aria-label={`Select ${orb.label} theme`}
            aria-pressed={theme === orb.theme}
          >
            <div
              className={cn(
                'w-10 h-10 rounded-full transition-all duration-200',
                orb.bgClass,
                theme === orb.theme
                  ? 'ring-2 ring-offset-2 ring-offset-[rgb(var(--background))] ring-[rgb(var(--accent))] scale-110 shadow-[0_0_20px_rgba(var(--accent-glow),0.5)]'
                  : 'hover:scale-105 hover:shadow-[0_0_15px_rgba(var(--accent-glow),0.3)]'
              )}
            />
            <span
              className={cn(
                'text-xs transition-colors',
                theme === orb.theme
                  ? 'text-[rgb(var(--accent))]'
                  : 'text-[rgb(var(--muted-foreground))] group-hover:text-[rgb(var(--foreground))]'
              )}
            >
              {orb.label}
            </span>
            {theme === orb.theme && (
              <div className="w-6 h-0.5 bg-[rgb(var(--accent))] rounded-full" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
