'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import { getStoredToken } from '@/lib/api';
import type {
  WebSocketMessage,
  WebSocketChannelType,
} from '@/types';

// Connection states
type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

interface WebSocketContextType {
  // Connection state
  connectionState: ConnectionState;
  isConnected: boolean;

  // Subscription management
  subscribe: (
    channel: WebSocketChannelType,
    params?: Record<string, string | number>,
    callback?: (message: WebSocketMessage) => void
  ) => () => void;
  unsubscribe: (channelId: string) => void;

  // Direct message sending (for ping/pong, etc.)
  send: (message: Record<string, unknown>) => void;

  // Last message per channel (for components that just need current state)
  lastMessages: Map<string, WebSocketMessage>;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

// Build WebSocket URL based on environment
function getWebSocketUrl(): string {
  if (typeof window === 'undefined') {
    return '';
  }

  // Use environment variable if available
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

  if (apiUrl) {
    // Convert http(s) to ws(s)
    const wsUrl = apiUrl.replace(/^http/, 'ws');
    return `${wsUrl}/ws`;
  }

  // Default: use current host with ws protocol
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/ws`;
}

// Build channel ID from type and params
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

interface Subscription {
  channelId: string;
  channelType: WebSocketChannelType;
  params?: Record<string, string | number>;
  callbacks: Set<(message: WebSocketMessage) => void>;
}

interface WebSocketProviderProps {
  children: ReactNode;
  autoConnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function WebSocketProvider({
  children,
  autoConnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
}: WebSocketProviderProps) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [lastMessages, setLastMessages] = useState<Map<string, WebSocketMessage>>(new Map());

  const wsRef = useRef<WebSocket | null>(null);
  const subscriptionsRef = useRef<Map<string, Subscription>>(new Map());
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = getWebSocketUrl();
    if (!wsUrl) return;

    // Add token if available
    const token = getStoredToken();
    const urlWithToken = token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl;

    setConnectionState('connecting');

    try {
      const ws = new WebSocket(urlWithToken);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState('connected');
        reconnectAttemptsRef.current = 0;

        // Re-subscribe to all channels
        subscriptionsRef.current.forEach((sub) => {
          ws.send(JSON.stringify({
            action: 'subscribe',
            channel: sub.channelType,
            params: sub.params,
          }));
        });

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          const channelId = message.channel;

          if (channelId) {
            // Update last message for this channel
            setLastMessages((prev) => {
              const next = new Map(prev);
              next.set(channelId, message);
              return next;
            });

            // Notify subscribers
            const subscription = subscriptionsRef.current.get(channelId);
            if (subscription) {
              subscription.callbacks.forEach((callback) => {
                try {
                  callback(message);
                } catch (err) {
                  console.error('WebSocket callback error:', err);
                }
              });
            }
          }
        } catch (err) {
          console.error('WebSocket message parse error:', err);
        }
      };

      ws.onclose = () => {
        setConnectionState('disconnected');

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        // Attempt reconnection
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          setConnectionState('reconnecting');
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (err) {
      console.error('WebSocket connection error:', err);
      setConnectionState('disconnected');
    }
  }, [reconnectInterval, maxReconnectAttempts]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState('disconnected');
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent auto-reconnect
  }, [maxReconnectAttempts]);

  // Subscribe to a channel
  const subscribe = useCallback((
    channel: WebSocketChannelType,
    params?: Record<string, string | number>,
    callback?: (message: WebSocketMessage) => void
  ): (() => void) => {
    const channelId = buildChannelId(channel, params);

    // Get or create subscription
    let subscription = subscriptionsRef.current.get(channelId);

    if (!subscription) {
      subscription = {
        channelId,
        channelType: channel,
        params,
        callbacks: new Set(),
      };
      subscriptionsRef.current.set(channelId, subscription);

      // Send subscribe message if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          action: 'subscribe',
          channel,
          params,
        }));
      }
    }

    // Add callback if provided
    if (callback) {
      subscription.callbacks.add(callback);
    }

    // Return unsubscribe function
    return () => {
      if (callback && subscription) {
        subscription.callbacks.delete(callback);
      }

      // If no more callbacks, unsubscribe from channel
      if (subscription && subscription.callbacks.size === 0) {
        subscriptionsRef.current.delete(channelId);

        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            action: 'unsubscribe',
            channel: channelId,
          }));
        }
      }
    };
  }, []);

  // Unsubscribe from a channel by ID
  const unsubscribe = useCallback((channelId: string) => {
    subscriptionsRef.current.delete(channelId);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'unsubscribe',
        channel: channelId,
      }));
    }
  }, []);

  // Send a message
  const send = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  const value: WebSocketContextType = {
    connectionState,
    isConnected: connectionState === 'connected',
    subscribe,
    unsubscribe,
    send,
    lastMessages,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
}
