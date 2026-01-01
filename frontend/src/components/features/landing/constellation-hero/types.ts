// Types for the Constellation Hero component

export interface ConstellationCard {
  id: string;
  name: string;
  setCode: string;
  imageUrl: string;
  price: number;
  priceChange: number; // percentage
}

export interface CardPosition {
  x: number;      // percentage from left (0-100)
  y: number;      // percentage from top (0-100)
  z: number;      // depth layer (0-1, higher = closer/larger)
  rotation: number; // degrees
}

export interface FloatingCardProps {
  card: ConstellationCard;
  position: CardPosition;
  index: number;
  mousePosition: { x: number; y: number };
  isVisible: boolean;
}

export interface PriceAnnotationProps {
  price: number;
  priceChange: number;
  delay: number;
  position: 'top' | 'bottom';
}

export interface MousePosition {
  x: number; // 0-1, normalized
  y: number; // 0-1, normalized
}
