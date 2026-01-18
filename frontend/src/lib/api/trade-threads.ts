/**
 * Trade Thread API functions for trade messaging.
 */
import { fetchApi } from './client';
import type { TradeStatus } from '@/types';

// =============================================================================
// Types
// =============================================================================

export interface TradeThreadMessage {
  id: number;
  thread_id: number;
  sender_id: number;
  sender_username: string;
  sender_display_name?: string;
  sender_avatar_url?: string;
  content?: string;
  card?: {
    id: number;
    name: string;
    set_code?: string;
    image_url?: string;
    price?: number;
  };
  has_attachments: boolean;
  attachments: Array<{
    id: number;
    file_url: string;
    file_type?: string;
  }>;
  reactions: Record<string, number[]>; // { "thumbs_up": [userId1, userId2] }
  created_at: string;
  deleted_at?: string;
  is_system_message: boolean;
}

export interface TradeThread {
  id: number;
  trade_id: number;
  messages: TradeThreadMessage[];
  created_at: string;
}

export interface TradeThreadSummary {
  id: number;
  status: TradeStatus;
  proposer_username: string;
  recipient_username: string;
  offer_card_count: number;
  offer_value: number;
  request_card_count: number;
  request_value: number;
  expires_at?: string;
}

export interface SendMessageRequest {
  content?: string;
  card_id?: number;
}

export interface UploadAttachmentResponse {
  id: number;
  file_url: string;
  file_type?: string;
}

export interface ToggleReactionResponse {
  reactions: Record<string, number[]>;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get or create a trade thread for a specific trade.
 */
export async function getTradeThread(tradeId: number): Promise<TradeThread> {
  return fetchApi(`/trades/${tradeId}/thread`);
}

/**
 * Get trade summary for the thread header.
 */
export async function getThreadSummary(tradeId: number): Promise<TradeThreadSummary> {
  return fetchApi(`/trades/${tradeId}/thread/summary`);
}

/**
 * Send a message to the trade thread.
 */
export async function sendMessage(
  tradeId: number,
  data: SendMessageRequest
): Promise<TradeThreadMessage> {
  return fetchApi(`/trades/${tradeId}/thread/messages`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Upload an image attachment to a message.
 */
export async function uploadAttachment(
  tradeId: number,
  messageId: number,
  file: File
): Promise<UploadAttachmentResponse> {
  const formData = new FormData();
  formData.append('file', file);

  // Use fetchApi without Content-Type header for FormData
  const url = `/trades/${tradeId}/thread/messages/${messageId}/attachments`;
  const response = await fetch(`/api${url}`, {
    method: 'POST',
    body: formData,
    headers: {
      Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(errorData.detail || 'Upload failed');
  }

  return response.json();
}

/**
 * Toggle a reaction on a message.
 */
export async function toggleReaction(
  tradeId: number,
  messageId: number,
  reactionType: string
): Promise<ToggleReactionResponse> {
  return fetchApi(`/trades/${tradeId}/thread/messages/${messageId}/reactions`, {
    method: 'POST',
    body: JSON.stringify({ reaction_type: reactionType }),
  });
}

/**
 * Soft delete a message.
 */
export async function deleteMessage(
  tradeId: number,
  messageId: number
): Promise<void> {
  await fetchApi(`/trades/${tradeId}/thread/messages/${messageId}`, {
    method: 'DELETE',
  });
}
