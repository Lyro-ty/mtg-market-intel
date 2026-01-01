import { ConstellationCard, CardPosition } from './types';

// Mana color definitions matching MTG's 5 colors
export type ManaColor = 'white' | 'blue' | 'black' | 'red' | 'green';

export interface ManaCard extends ConstellationCard {
  manaColor: ManaColor;
}

// 5 iconic cards representing each mana color
// Arranged like the back of an MTG card (WUBRG order in a pentagon)
export const manaCards: ManaCard[] = [
  {
    id: 'swords-to-plowshares',
    name: 'Swords to Plowshares',
    setCode: 'MH3',
    imageUrl: 'https://cards.scryfall.io/normal/front/0/4/04e0738b-b856-401e-8b41-096e2c48cf96.jpg',
    price: 4.50,
    priceChange: 2.1,
    manaColor: 'white',
  },
  {
    id: 'force-of-will',
    name: 'Force of Will',
    setCode: 'ALL',
    imageUrl: 'https://cards.scryfall.io/normal/front/d/d/dd60b291-0a88-4e8e-bef8-76cdfd6c8183.jpg',
    price: 89.99,
    priceChange: -1.2,
    manaColor: 'blue',
  },
  {
    id: 'sheoldred',
    name: 'Sheoldred, the Apocalypse',
    setCode: 'DMU',
    imageUrl: 'https://cards.scryfall.io/normal/front/d/6/d67be074-cdd4-41d9-ac89-0a0456c4e4b2.jpg',
    price: 89.00,
    priceChange: -3.5,
    manaColor: 'black',
  },
  {
    id: 'ragavan',
    name: 'Ragavan, Nimble Pilferer',
    setCode: 'MH2',
    imageUrl: 'https://cards.scryfall.io/normal/front/a/9/a9738cda-adb1-47fb-9f4c-ecd930228c4d.jpg',
    price: 62.50,
    priceChange: 5.8,
    manaColor: 'red',
  },
  {
    id: 'craterhoof',
    name: 'Craterhoof Behemoth',
    setCode: 'AVR',
    imageUrl: 'https://cards.scryfall.io/normal/front/4/4/44afd414-cc69-4888-ba12-7ea87e60b1f7.jpg',
    price: 45.00,
    priceChange: 8.7,
    manaColor: 'green',
  },
];

// Mana color CSS values (matching MTG official colors)
export const manaColors: Record<ManaColor, { primary: string; glow: string }> = {
  white: {
    primary: '255 251 230',    // Warm white/cream
    glow: '255 251 213',
  },
  blue: {
    primary: '14 104 171',     // MTG blue
    glow: '59 130 246',
  },
  black: {
    primary: '75 70 80',       // Dark purple-gray
    glow: '139 92 246',
  },
  red: {
    primary: '211 32 42',      // MTG red
    glow: '239 68 68',
  },
  green: {
    primary: '0 115 62',       // MTG green
    glow: '34 197 94',
  },
};

// Pentagon positions for 5 cards (WUBRG order starting from top)
// Calculated for a circle with radius ~30% of container, centered
const RADIUS = 30; // percentage from center - balanced for rotation
const CENTER_X = 50;
const CENTER_Y = 50;
const START_ANGLE = -90; // Start from top (12 o'clock position)

export const getCircularPositions = (): CardPosition[] => {
  return manaCards.map((_, index) => {
    // Pentagon: 72 degrees apart (360/5)
    const angle = START_ANGLE + (index * 72);
    const radians = (angle * Math.PI) / 180;

    return {
      x: CENTER_X + RADIUS * Math.cos(radians),
      y: CENTER_Y + RADIUS * Math.sin(radians),
      z: 0.85, // All at similar depth
      rotation: (index - 2) * 3, // Subtle rotation: -6, -3, 0, 3, 6
    };
  });
};

// Export radius and center for other components to use
export const PENTAGON_RADIUS = RADIUS;
export const PENTAGON_CENTER = { x: CENTER_X, y: CENTER_Y };

export const cardPositions = getCircularPositions();

// Mobile: Show only 3 cards (White, Black, Green - a triangle)
export const mobileCardIndices = [0, 2, 4];
export const mobileCardPositions: CardPosition[] = [
  { x: 50, y: 15, z: 0.85, rotation: 0 },    // Top center (White)
  { x: 20, y: 70, z: 0.85, rotation: -8 },   // Bottom left (Black)
  { x: 80, y: 70, z: 0.85, rotation: 8 },    // Bottom right (Green)
];

// Legacy export for compatibility
export const curatedCards = manaCards;
