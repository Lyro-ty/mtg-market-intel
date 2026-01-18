'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { ReactNode, useMemo } from 'react';

export type FrameTier = 'bronze' | 'silver' | 'gold' | 'platinum' | 'legendary';

interface FrameEffectsProps {
  tier: FrameTier;
  children: ReactNode;
  className?: string;
  isHovered?: boolean;
}

// Frame styling configuration per tier
const tierFrameStyles: Record<FrameTier, {
  borderColor: string;
  shadowColor: string;
  glowIntensity: string;
  bgGradient?: string;
  animated?: boolean;
}> = {
  bronze: {
    borderColor: 'border-amber-700',
    shadowColor: 'shadow-amber-900/20',
    glowIntensity: '',
  },
  silver: {
    borderColor: 'border-gray-400',
    shadowColor: 'shadow-gray-500/30',
    glowIntensity: 'shadow-md',
  },
  gold: {
    borderColor: 'border-yellow-500',
    shadowColor: 'shadow-yellow-500/40',
    glowIntensity: 'shadow-lg shadow-yellow-500/30',
    bgGradient: 'from-yellow-500/5 via-transparent to-yellow-500/5',
  },
  platinum: {
    borderColor: 'border-cyan-400',
    shadowColor: 'shadow-cyan-400/50',
    glowIntensity: 'shadow-xl shadow-cyan-400/40',
    bgGradient: 'from-cyan-400/10 via-transparent to-cyan-400/10',
    animated: true,
  },
  legendary: {
    borderColor: 'border-purple-500',
    shadowColor: 'shadow-purple-500/60',
    glowIntensity: 'shadow-2xl shadow-purple-500/50',
    bgGradient: 'from-purple-500/15 via-transparent to-purple-500/15',
    animated: true,
  },
};

// Particle effect for legendary tier
function ParticleEffect() {
  const particles = useMemo(() =>
    Array.from({ length: 12 }, (_, i) => ({
      id: i,
      delay: Math.random() * 2,
      duration: 2 + Math.random() * 2,
      x: Math.random() * 100,
    })), []
  );

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute w-1 h-1 rounded-full bg-purple-400/70"
          style={{
            left: `${particle.x}%`,
            bottom: 0,
          }}
          animate={{
            y: [0, -100, -150],
            opacity: [0, 1, 0],
            scale: [0.5, 1, 0.3],
          }}
          transition={{
            duration: particle.duration,
            delay: particle.delay,
            repeat: Infinity,
            ease: 'easeOut',
          }}
        />
      ))}
    </div>
  );
}

// Shimmer effect for platinum tier
function ShimmerEffect() {
  return (
    <motion.div
      className="absolute inset-0 pointer-events-none"
      style={{
        background: 'linear-gradient(90deg, transparent 0%, rgba(103, 232, 249, 0.15) 50%, transparent 100%)',
      }}
      animate={{
        x: ['-100%', '200%'],
      }}
      transition={{
        duration: 3,
        repeat: Infinity,
        ease: 'linear',
      }}
    />
  );
}

export function FrameEffects({
  tier,
  children,
  className,
  isHovered = false,
}: FrameEffectsProps) {
  const frameStyle = tierFrameStyles[tier];
  const showParticles = tier === 'legendary';
  const showShimmer = tier === 'platinum';

  return (
    <div
      className={cn(
        // Base frame styles
        'relative rounded-xl border-2 overflow-hidden',
        frameStyle.borderColor,
        frameStyle.glowIntensity,
        // Background gradient for higher tiers
        frameStyle.bgGradient && `bg-gradient-to-br ${frameStyle.bgGradient}`,
        // Hover effects for non-bronze tiers
        tier !== 'bronze' && 'transition-all duration-300',
        tier !== 'bronze' && isHovered && 'scale-[1.02]',
        // Tier-specific hover glow enhancement
        tier === 'silver' && isHovered && 'shadow-lg shadow-gray-400/40',
        tier === 'gold' && isHovered && 'shadow-xl shadow-yellow-400/50',
        tier === 'platinum' && isHovered && 'shadow-2xl shadow-cyan-300/60',
        tier === 'legendary' && isHovered && 'shadow-2xl shadow-purple-400/70',
        className
      )}
    >
      {/* Inner glow border for higher tiers */}
      {(tier === 'gold' || tier === 'platinum' || tier === 'legendary') && (
        <div
          className={cn(
            'absolute inset-0 rounded-xl pointer-events-none',
            tier === 'gold' && 'ring-1 ring-inset ring-yellow-400/30',
            tier === 'platinum' && 'ring-1 ring-inset ring-cyan-300/40',
            tier === 'legendary' && 'ring-2 ring-inset ring-purple-400/50'
          )}
        />
      )}

      {/* Shimmer effect for platinum */}
      {showShimmer && <ShimmerEffect />}

      {/* Particle effect for legendary */}
      {showParticles && <ParticleEffect />}

      {/* Animated border glow for legendary */}
      {tier === 'legendary' && (
        <motion.div
          className="absolute inset-0 rounded-xl pointer-events-none"
          animate={{
            boxShadow: [
              'inset 0 0 20px rgba(139, 92, 246, 0.2)',
              'inset 0 0 30px rgba(139, 92, 246, 0.4)',
              'inset 0 0 20px rgba(139, 92, 246, 0.2)',
            ],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      )}

      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
    </div>
  );
}

export default FrameEffects;
