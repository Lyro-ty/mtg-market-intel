'use client';

import Image from 'next/image';
import { motion, useSpring, useTransform } from 'framer-motion';
import { FloatingCardProps } from './types';
import { PriceAnnotation } from './PriceAnnotation';
import { manaColors, ManaColor } from './cardData';
import { cn } from '@/lib/utils';

interface ManaFloatingCardProps extends FloatingCardProps {
  manaColor?: ManaColor;
}

export function FloatingCard({
  card,
  position,
  index,
  mousePosition,
  isVisible,
  manaColor,
}: ManaFloatingCardProps) {
  // Get mana-specific colors
  const colors = manaColor ? manaColors[manaColor] : null;

  // Calculate parallax offset based on mouse position and depth
  const parallaxStrength = position.z * 15; // Reduced for circular layout

  // Use springs for smooth mouse following
  const springConfig = { stiffness: 50, damping: 20, mass: 1 };
  const mouseX = useSpring(mousePosition.x, springConfig);
  const mouseY = useSpring(mousePosition.y, springConfig);

  // Transform mouse position to offset values
  const offsetX = useTransform(mouseX, [0, 1], [-parallaxStrength, parallaxStrength]);
  const offsetY = useTransform(mouseY, [0, 1], [-parallaxStrength * 0.6, parallaxStrength * 0.6]);

  // Card size for image sizing hints
  const cardSize = 120;

  // Staggered entrance delay
  const entranceDelay = index * 0.15;

  // Float animation - gentle bobbing
  const floatDuration = 4 + (index % 3); // 4-6 seconds
  const floatDelay = index * 0.3;

  return (
    <motion.div
      className="pointer-events-auto w-full h-full"
      style={{
        x: offsetX,
        y: offsetY,
      }}
      initial={{
        opacity: 0,
        scale: 0.3,
        rotate: position.rotation - 15,
      }}
      animate={isVisible ? {
        opacity: 1,
        scale: 1,
        rotate: position.rotation,
      } : {
        opacity: 0,
        scale: 0.3,
        rotate: position.rotation - 15,
      }}
      transition={{
        delay: entranceDelay,
        duration: 0.8,
        ease: [0.23, 1, 0.32, 1],
      }}
      whileHover={{
        scale: 1.15,
        zIndex: 100,
        transition: { duration: 0.3 },
      }}
    >
      {/* Floating animation wrapper */}
      <motion.div
        animate={{
          y: [0, -6, 0],
        }}
        transition={{
          duration: floatDuration,
          delay: floatDelay,
          repeat: Infinity,
          repeatType: 'loop',
          ease: 'easeInOut',
        }}
        className="relative group"
      >
        {/* Mana-colored glow effect */}
        <motion.div
          className="absolute -inset-3 rounded-xl blur-xl"
          style={{
            background: colors
              ? `radial-gradient(circle, rgb(${colors.glow}) 0%, transparent 70%)`
              : 'radial-gradient(circle, rgb(var(--magic-gold)) 0%, transparent 70%)',
          }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.4 }}
          whileHover={{ opacity: 0.7 }}
          transition={{ duration: 0.3 }}
        />

        {/* Card image container */}
        <div
          className={cn(
            'relative aspect-[5/7] rounded-lg overflow-hidden',
            'shadow-2xl shadow-black/50',
            'transition-all duration-300',
            'group-hover:shadow-[0_0_30px_rgba(var(--magic-gold),0.4)]'
          )}
          style={{
            border: colors
              ? `2px solid rgb(${colors.primary})`
              : '2px solid rgb(var(--magic-gold))',
          }}
        >
          {/* Foil shimmer overlay */}
          <motion.div
            className="absolute inset-0 z-10 pointer-events-none"
            style={{
              background: `linear-gradient(
                135deg,
                transparent 0%,
                rgba(255,255,255,0.1) 45%,
                rgba(255,255,255,0.2) 50%,
                rgba(255,255,255,0.1) 55%,
                transparent 100%
              )`,
              backgroundSize: '200% 200%',
            }}
            animate={{
              backgroundPosition: ['0% 0%', '200% 200%'],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: 'linear',
            }}
          />

          {/* Card image */}
          <Image
            src={card.imageUrl}
            alt={card.name}
            fill
            className="object-cover"
            sizes={`${cardSize}px`}
            priority={index < 5}
            unoptimized
          />
        </div>

        {/* Price annotation */}
        <PriceAnnotation
          price={card.price}
          priceChange={card.priceChange}
          delay={entranceDelay}
        />
      </motion.div>
    </motion.div>
  );
}
