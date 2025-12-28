import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        success:
          "border-transparent bg-[rgb(var(--success))]/20 text-[rgb(var(--success))]",
        warning:
          "border-transparent bg-[rgb(var(--warning))]/20 text-[rgb(var(--warning))]",
        danger:
          "border-transparent bg-[rgb(var(--destructive))]/20 text-[rgb(var(--destructive))]",
        info:
          "border-transparent bg-[rgb(var(--info))]/20 text-[rgb(var(--info))]",
        accent:
          "bg-accent/15 text-accent border-accent",
      },
      size: {
        sm: "text-xs px-2 py-0.5",
        md: "text-sm px-2.5 py-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "sm",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props} />
  )
}

// Action badge helper for BUY/SELL/HOLD recommendations
function ActionBadge({ action }: { action: string }) {
  const variant = {
    BUY: 'success',
    SELL: 'danger',
    HOLD: 'warning',
  }[action] as 'success' | 'danger' | 'warning';

  return <Badge variant={variant}>{action}</Badge>;
}

export { Badge, ActionBadge, badgeVariants }
