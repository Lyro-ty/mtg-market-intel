'use client';

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Base Skeleton component with shimmer animation
 * Used as a placeholder while content is loading
 */
export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-shimmer bg-gradient-to-r from-[rgb(var(--secondary))] via-[rgba(var(--accent),0.08)] to-[rgb(var(--secondary))] bg-[length:200%_100%] rounded',
        className
      )}
      style={style}
    />
  );
}

/**
 * Card skeleton for loading card-style content
 */
export function CardSkeleton() {
  return (
    <div className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-6 space-y-4">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

/**
 * Stats skeleton for loading stats/metrics grids
 */
export function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4 space-y-2"
        >
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-8 w-24" />
        </div>
      ))}
    </div>
  );
}

/**
 * Chart skeleton for loading chart/graph placeholders
 */
export function ChartSkeleton({ height = 'h-64' }: { height?: string }) {
  return (
    <div
      className={cn(
        'rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] p-6',
        height
      )}
    >
      {/* Chart header */}
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-32" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16 rounded-md" />
          <Skeleton className="h-6 w-16 rounded-md" />
        </div>
      </div>
      {/* Chart area */}
      <div className="flex items-end justify-between h-[calc(100%-3rem)] gap-2">
        {[...Array(12)].map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1 rounded-t-sm"
            style={{ height: `${20 + Math.random() * 70}%` }}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Table row skeleton for loading table data
 */
export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="border-b border-[rgb(var(--border))]">
      {[...Array(columns)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton
            className={cn(
              'h-4',
              i === 0 ? 'w-32' : i === columns - 1 ? 'w-16' : 'w-20'
            )}
          />
        </td>
      ))}
    </tr>
  );
}

/**
 * Table skeleton for loading entire tables
 */
export function TableSkeleton({ rows = 5, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--card))] overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[rgb(var(--border))] bg-[rgb(var(--secondary))]">
            {[...Array(columns)].map((_, i) => (
              <th key={i} className="px-4 py-3 text-left">
                <Skeleton className="h-3 w-16" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...Array(rows)].map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * List item skeleton for loading list items
 */
export function ListItemSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 border-b border-[rgb(var(--border))]">
      <Skeleton className="h-12 w-12 rounded-lg" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-6 w-20" />
    </div>
  );
}

/**
 * Page skeleton with header and content areas
 */
export function PageSkeleton() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>
      {/* Stats row */}
      <StatsSkeleton />
      {/* Content area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartSkeleton />
        <CardSkeleton />
      </div>
    </div>
  );
}
