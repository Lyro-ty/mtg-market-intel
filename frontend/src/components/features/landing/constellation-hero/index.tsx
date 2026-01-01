'use client';

import { useState, useEffect } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { useMouseParallax } from './useMouseParallax';
import { FloatingCard } from './FloatingCard';
import { ConstellationLines } from './ConstellationLines';
import { HeroContent } from './HeroContent';
import {
  manaCards,
  cardPositions,
  mobileCardPositions,
  mobileCardIndices,
  manaColors,
} from './cardData';

export function ConstellationHero() {
  const [isVisible, setIsVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const prefersReducedMotion = useReducedMotion();

  // Mouse parallax hook
  const { mousePosition, containerRef } = useMouseParallax({
    enabled: !isMobile && !prefersReducedMotion,
  });

  // Detect mobile on mount
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Trigger entrance animation after mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // Select cards and positions based on viewport
  const displayCards = isMobile
    ? mobileCardIndices.map(i => manaCards[i])
    : manaCards;
  const positions = isMobile ? mobileCardPositions : cardPositions;

  return (
    <section
      ref={containerRef}
      className="relative min-h-screen overflow-hidden bg-[rgb(var(--background))]"
    >
      {/* Background gradient layers */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Deep space gradient */}
        <div className="absolute inset-0 bg-gradient-to-b from-[rgb(var(--background))] via-[rgb(8,8,14)] to-[rgb(var(--background))]" />

        {/* Mana-colored ambient orbs - positioned around the pentagon */}
        {/* White - top */}
        <motion.div
          className="absolute top-[15%] left-1/2 -translate-x-1/2 w-64 h-64 rounded-full blur-[120px]"
          style={{ background: `rgb(${manaColors.white.glow})` }}
          animate={prefersReducedMotion ? {} : {
            opacity: [0.08, 0.15, 0.08],
            scale: [1, 1.1, 1],
          }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
        />
        {/* Blue - top right */}
        <motion.div
          className="absolute top-[30%] right-[15%] w-56 h-56 rounded-full blur-[100px]"
          style={{ background: `rgb(${manaColors.blue.glow})` }}
          animate={prefersReducedMotion ? {} : {
            opacity: [0.1, 0.2, 0.1],
            scale: [1, 1.15, 1],
          }}
          transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        />
        {/* Black - bottom right */}
        <motion.div
          className="absolute bottom-[25%] right-[20%] w-60 h-60 rounded-full blur-[110px]"
          style={{ background: `rgb(${manaColors.black.glow})` }}
          animate={prefersReducedMotion ? {} : {
            opacity: [0.12, 0.22, 0.12],
            scale: [1, 1.1, 1],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        />
        {/* Red - bottom left */}
        <motion.div
          className="absolute bottom-[25%] left-[20%] w-52 h-52 rounded-full blur-[100px]"
          style={{ background: `rgb(${manaColors.red.glow})` }}
          animate={prefersReducedMotion ? {} : {
            opacity: [0.1, 0.18, 0.1],
            scale: [1, 1.12, 1],
          }}
          transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
        />
        {/* Green - top left */}
        <motion.div
          className="absolute top-[30%] left-[15%] w-56 h-56 rounded-full blur-[100px]"
          style={{ background: `rgb(${manaColors.green.glow})` }}
          animate={prefersReducedMotion ? {} : {
            opacity: [0.1, 0.2, 0.1],
            scale: [1, 1.15, 1],
          }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 4 }}
        />
      </div>

      {/* Rotating pentagram container - fixed to viewport height so lines stay visible */}
      <div className="absolute inset-x-0 top-0 h-screen z-[16]">
        <motion.div
          className="absolute inset-0"
          animate={prefersReducedMotion ? {} : {
            rotate: [0, 360],
          }}
          transition={{
            duration: 120, // Very slow rotation - 2 minutes per revolution
            repeat: Infinity,
            ease: 'linear',
          }}
          style={{ transformOrigin: 'center center' }}
        >
          {/* Pentagram lines connecting all cards */}
          <ConstellationLines positions={positions} isVisible={isVisible} />

          {/* Cards at each vertex - counter-rotate to stay upright */}
          {displayCards.map((card, index) => {
            const pos = positions[index];
            // Card is 120px wide, aspect ratio 5:7 = 168px tall
            // Center card on vertex point
            const cardWidth = 120;
            const cardHeight = 168;
            return (
              <motion.div
                key={card.id}
                className="absolute"
                style={{
                  left: `${pos.x}%`,
                  top: `${pos.y}%`,
                  marginLeft: -cardWidth / 2,
                  marginTop: -cardHeight / 2,
                  width: cardWidth,
                  height: cardHeight,
                }}
                animate={prefersReducedMotion ? {} : {
                  rotate: [0, -360], // Counter-rotate to stay upright
                }}
                transition={{
                  duration: 120,
                  repeat: Infinity,
                  ease: 'linear',
                }}
              >
                <FloatingCard
                  card={card}
                  position={{ ...pos, x: 50, y: 50 }} // Center within this container
                  index={index}
                  mousePosition={mousePosition}
                  isVisible={isVisible}
                  manaColor={card.manaColor}
                />
              </motion.div>
            );
          })}
        </motion.div>
      </div>

      {/* Center gradient for content readability - larger opaque area so cards don't obscure text */}
      <div className="absolute inset-0 z-[17] pointer-events-none">
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse 60% 50% at center, rgb(var(--background)) 0%, rgb(var(--background)) 40%, transparent 70%)',
        }} />
      </div>

      {/* Hero content */}
      <div className="relative z-20 flex items-center justify-center min-h-screen py-20">
        <HeroContent />
      </div>

      {/* Bottom fade */}
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[rgb(var(--background))] to-transparent z-30 pointer-events-none" />
    </section>
  );
}

// Export as default for easier imports
export default ConstellationHero;
