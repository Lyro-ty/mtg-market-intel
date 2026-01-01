'use client';

import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PriceAnnotationProps {
  price: number;
  priceChange: number;
  delay: number;
  className?: string;
}

export function PriceAnnotation({ price, priceChange, delay, className }: PriceAnnotationProps) {
  const isPositive = priceChange >= 0;
  const formattedPrice = price >= 1000
    ? `$${(price / 1000).toFixed(0)}K`
    : `$${price.toFixed(0)}`;
  const formattedChange = `${isPositive ? '+' : ''}${priceChange.toFixed(1)}%`;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{
        delay: delay + 0.5, // Wait for card entrance + 0.5s
        duration: 0.4,
        ease: 'easeOut',
      }}
      className={cn(
        'absolute -bottom-2 left-1/2 -translate-x-1/2 translate-y-full',
        'flex items-center gap-1.5 px-2 py-1',
        'bg-[rgb(var(--card))]/90 backdrop-blur-sm',
        'border border-[rgb(var(--border))]/50 rounded-md',
        'shadow-lg shadow-black/20',
        'whitespace-nowrap',
        className
      )}
    >
      <span className="text-xs font-semibold text-[rgb(var(--foreground))]">
        {formattedPrice}
      </span>
      <span
        className={cn(
          'flex items-center gap-0.5 text-xs font-medium',
          isPositive ? 'text-[rgb(var(--success))]' : 'text-[rgb(var(--destructive))]'
        )}
      >
        {isPositive ? (
          <TrendingUp className="w-3 h-3" />
        ) : (
          <TrendingDown className="w-3 h-3" />
        )}
        {formattedChange}
      </span>
    </motion.div>
  );
}
