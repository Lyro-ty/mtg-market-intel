'use client';

import { useEffect, useState, useCallback } from 'react';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import type {
  WebSocketMessage,
  WebSocketChannelType,
  MarketUpdateMessage,
  CardUpdateMessage,
  DashboardUpdateMessage,
  InventoryUpdateMessage,
  RecommendationsUpdateMessage,
} from '@/types';

/**
 * Generic hook for subscribing to any WebSocket channel.
 *
 * @param channel - The channel type to subscribe to
 * @param params - Optional parameters for the channel
 * @param onMessage - Optional callback for new messages
 * @returns The last message received on this channel
 */
export function useWebSocket<T extends WebSocketMessage = WebSocketMessage>(
  channel: WebSocketChannelType,
  params?: Record<string, string | number>,
  onMessage?: (message: T) => void
): T | null {
  const { subscribe, lastMessages, isConnected } = useWebSocketContext();
  const [lastMessage, setLastMessage] = useState<T | null>(null);

  // Build channel ID to check lastMessages
  const channelId = buildChannelId(channel, params);

  useEffect(() => {
    const callback = (message: WebSocketMessage) => {
      setLastMessage(message as T);
      onMessage?.(message as T);
    };

    const unsubscribe = subscribe(channel, params, callback);

    // Check if we have a cached message
    const cached = lastMessages.get(channelId);
    if (cached) {
      setLastMessage(cached as T);
    }

    return unsubscribe;
  }, [channel, params, subscribe, onMessage, lastMessages, channelId]);

  return lastMessage;
}

/**
 * Hook for subscribing to market index updates.
 *
 * @param currency - Currency code (default: USD)
 * @param onUpdate - Optional callback for updates
 */
export function useMarketUpdates(
  currency: string = 'USD',
  onUpdate?: (message: MarketUpdateMessage) => void
): MarketUpdateMessage | null {
  return useWebSocket<MarketUpdateMessage>(
    'market',
    { currency },
    onUpdate
  );
}

/**
 * Hook for subscribing to individual card price updates.
 *
 * @param cardId - The card ID to watch
 * @param onUpdate - Optional callback for updates
 */
export function useCardUpdates(
  cardId: number,
  onUpdate?: (message: CardUpdateMessage) => void
): CardUpdateMessage | null {
  return useWebSocket<CardUpdateMessage>(
    'card',
    { card_id: cardId },
    onUpdate
  );
}

/**
 * Hook for subscribing to dashboard section updates.
 *
 * @param currency - Currency code (default: USD)
 * @param onUpdate - Optional callback for updates
 */
export function useDashboardUpdates(
  currency: string = 'USD',
  onUpdate?: (message: DashboardUpdateMessage) => void
): DashboardUpdateMessage | null {
  return useWebSocket<DashboardUpdateMessage>(
    'dashboard',
    { currency },
    onUpdate
  );
}

/**
 * Hook for subscribing to inventory updates (requires auth).
 *
 * @param userId - The user ID (from auth context)
 * @param onUpdate - Optional callback for updates
 */
export function useInventoryUpdates(
  userId: number,
  onUpdate?: (message: InventoryUpdateMessage) => void
): InventoryUpdateMessage | null {
  return useWebSocket<InventoryUpdateMessage>(
    'inventory',
    { user_id: userId },
    onUpdate
  );
}

/**
 * Hook for subscribing to new recommendation alerts.
 *
 * @param onUpdate - Optional callback for updates
 */
export function useRecommendationUpdates(
  onUpdate?: (message: RecommendationsUpdateMessage) => void
): RecommendationsUpdateMessage | null {
  return useWebSocket<RecommendationsUpdateMessage>(
    'recommendations',
    undefined,
    onUpdate
  );
}

/**
 * Hook to get WebSocket connection status.
 */
export function useWebSocketStatus() {
  const { connectionState, isConnected } = useWebSocketContext();
  return { connectionState, isConnected };
}

// Helper to build channel ID (duplicated from context for convenience)
function buildChannelId(
  channel: WebSocketChannelType,
  params?: Record<string, string | number>
): string {
  switch (channel) {
    case 'market':
      return `channel:market:${params?.currency || 'USD'}`;
    case 'card':
      return `channel:card:${params?.card_id}`;
    case 'dashboard':
      return `channel:dashboard:${params?.currency || 'USD'}`;
    case 'inventory':
      return `channel:inventory:user:${params?.user_id}`;
    case 'recommendations':
      return 'channel:recommendations';
    default:
      return `channel:${channel}`;
  }
}
