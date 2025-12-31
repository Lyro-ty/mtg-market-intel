/**
 * Messages API functions for direct messaging.
 */
import { fetchApi } from './client';

export interface Message {
  id: number;
  sender_id: number;
  recipient_id: number;
  content: string;
  read_at: string | null;
  created_at: string;
}

export interface ConversationSummary {
  user_id: number;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  last_message: string;
  last_message_at: string;
  unread_count: number;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

export interface MessageListResponse {
  messages: Message[];
  has_more: boolean;
}

export interface SendMessageData {
  recipient_id: number;
  content: string;
}

/**
 * Send a message to a connected user.
 */
export async function sendMessage(data: SendMessageData): Promise<Message> {
  return fetchApi('/messages/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Get list of conversations with last message.
 */
export async function getConversations(): Promise<ConversationListResponse> {
  return fetchApi('/messages/conversations');
}

/**
 * Get messages with a specific user.
 */
export async function getConversation(
  userId: number,
  limit: number = 50,
  beforeId?: number
): Promise<MessageListResponse> {
  let url = `/messages/with/${userId}?limit=${limit}`;
  if (beforeId) {
    url += `&before_id=${beforeId}`;
  }
  return fetchApi(url);
}

/**
 * Get total unread message count.
 */
export async function getUnreadCount(): Promise<{ unread_count: number }> {
  return fetchApi('/messages/unread-count');
}

/**
 * Mark a specific message as read.
 */
export async function markMessageRead(
  messageId: number
): Promise<{ status: string }> {
  return fetchApi(`/messages/${messageId}/read`, {
    method: 'POST',
  });
}
