'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { CardPosition } from './types';
import { manaColors, ManaColor } from './cardData';

interface ConstellationLinesProps {
  positions: CardPosition[];
  isVisible: boolean;
}

// Generate all-to-all connections for pentagram pattern
function generatePentagramConnections(numCards: number): [number, number][] {
  const connections: [number, number][] = [];
  for (let i = 0; i < numCards; i++) {
    for (let j = i + 1; j < numCards; j++) {
      connections.push([i, j]);
    }
  }
  return connections;
}

// Mana colors in WUBRG order
const manaColorOrder: ManaColor[] = ['white', 'blue', 'black', 'red', 'green'];

export function ConstellationLines({ positions, isVisible }: ConstellationLinesProps) {
  // Generate connections based on number of cards
  const connections = useMemo(() => generatePentagramConnections(positions.length), [positions.length]);

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ overflow: 'visible' }}
    >
      <defs>
        {/* Create a gradient for each connection - using userSpaceOnUse for proper horizontal line rendering */}
        {connections.map(([startIdx, endIdx]) => {
          const startColor = manaColors[manaColorOrder[startIdx % 5]];
          const endColor = manaColors[manaColorOrder[endIdx % 5]];
          const start = positions[startIdx];
          const end = positions[endIdx];
          return (
            <linearGradient
              key={`gradient-${startIdx}-${endIdx}`}
              id={`lineGradient-${startIdx}-${endIdx}`}
              gradientUnits="userSpaceOnUse"
              x1={`${start.x}%`}
              y1={`${start.y}%`}
              x2={`${end.x}%`}
              y2={`${end.y}%`}
            >
              <stop offset="0%" stopColor={`rgb(${startColor.glow})`} stopOpacity="0.8" />
              <stop offset="100%" stopColor={`rgb(${endColor.glow})`} stopOpacity="0.8" />
            </linearGradient>
          );
        })}

        {/* Glow filter */}
        <filter id="pentagramGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Render connection lines - pentagram pattern */}
      {connections.map(([startIdx, endIdx], index) => {
        const start = positions[startIdx];
        const end = positions[endIdx];
        if (!start || !end) return null;

        // Skip 2-3 connection - rendered separately as static line due to motion.line bug
        if (startIdx === 2 && endIdx === 3) return null;

        const delay = 0.5 + index * 0.08;

        return (
          <motion.line
            key={`${startIdx}-${endIdx}`}
            x1={`${start.x}%`}
            y1={`${start.y}%`}
            x2={`${end.x}%`}
            y2={`${end.y}%`}
            stroke={
              // Use solid color for horizontal lines (gradient bug workaround)
              Math.abs(start.y - end.y) < 0.01
                ? `rgb(${manaColors[manaColorOrder[startIdx % 5]].glow})`
                : `url(#lineGradient-${startIdx}-${endIdx})`
            }
            strokeWidth="3"
            strokeLinecap="round"
            filter="url(#pentagramGlow)"
            initial={{ opacity: 0 }}
            animate={isVisible ? { opacity: 1 } : { opacity: 0 }}
            transition={{
              opacity: {
                delay,
                duration: 0.8,
                ease: 'easeOut',
              },
            }}
          />
        );
      })}

      {/* Static line for 2-3 connection (Black to Red) - filter causes issues with horizontal gradients */}
      {positions[2] && positions[3] && (
        <line
          x1={`${positions[2].x}%`}
          y1={`${positions[2].y}%`}
          x2={`${positions[3].x}%`}
          y2={`${positions[3].y}%`}
          stroke="url(#lineGradient-2-3)"
          strokeWidth="3"
          strokeLinecap="round"
          opacity="1"
        />
      )}

      {/* Mana-colored dots at each vertex */}
      {positions.map((pos, i) => {
        const color = manaColors[manaColorOrder[i % 5]];
        return (
          <motion.circle
            key={`dot-${i}`}
            cx={`${pos.x}%`}
            cy={`${pos.y}%`}
            r="6"
            fill={`rgb(${color.glow})`}
            filter="url(#pentagramGlow)"
            initial={{ scale: 0, opacity: 0 }}
            animate={isVisible ? { scale: 1, opacity: 0.9 } : { scale: 0, opacity: 0 }}
            transition={{ duration: 0.4, delay: 1.5 + i * 0.1 }}
          />
        );
      })}
    </svg>
  );
}
