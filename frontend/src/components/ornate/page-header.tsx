// frontend/src/components/ornate/page-header.tsx
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, subtitle, children, className }: PageHeaderProps) {
  return (
    <div className={cn('relative mb-8 pb-6', className)}>
      {/* Background glow */}
      <div className="absolute inset-0 bg-gradient-to-b from-[rgb(var(--accent))]/5 to-transparent rounded-lg" />

      <div className="relative flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl md:text-4xl text-foreground tracking-wide">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-2 text-muted-foreground">{subtitle}</p>
          )}
        </div>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>

      {/* Bottom gradient line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-[rgb(var(--accent))]/50 via-[rgb(var(--magic-gold))]/30 to-transparent" />
    </div>
  );
}
