import { cn } from '@/lib/utils';
import { cva, type VariantProps } from 'class-variance-authority';
import { type ButtonHTMLAttributes, forwardRef } from 'react';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md text-sm font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[rgb(var(--accent))] focus:ring-offset-[rgb(var(--background))] disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        default:
          'bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-glow))] hover:shadow-[0_0_20px_rgba(var(--accent),0.4)] hover:scale-[1.02] active:scale-[0.98]',
        // Alias for backward compatibility
        primary:
          'bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-glow))] hover:shadow-[0_0_20px_rgba(var(--accent),0.4)] hover:scale-[1.02] active:scale-[0.98]',
        secondary:
          'border border-[rgb(var(--accent))] text-[rgb(var(--accent))] hover:bg-[rgba(var(--accent),0.1)] hover:scale-[1.02] active:scale-[0.98]',
        ghost:
          'text-[rgb(var(--accent))] hover:underline hover:scale-[1.02]',
        destructive:
          'bg-red-600 text-white hover:bg-red-700 hover:scale-[1.02] active:scale-[0.98]',
        // Alias for backward compatibility
        danger:
          'bg-red-600 text-white hover:bg-red-700 hover:scale-[1.02] active:scale-[0.98]',
        outline:
          'border border-[rgb(var(--border))] hover:bg-[rgb(var(--surface))] hover:scale-[1.02] active:scale-[0.98]',
        link: 'text-[rgb(var(--accent))] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 py-2 px-4',
        sm: 'h-9 px-3',
        lg: 'h-11 px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export { buttonVariants };
