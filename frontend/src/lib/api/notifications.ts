/**
 * Notifications API functions
 */
import type { NotificationList, UnreadCount } from '@/types';
import { fetchApi } from './client';

export async function getNotifications(params?: {
  unread_only?: boolean;
  limit?: number;
}): Promise<NotificationList> {
  const searchParams = new URLSearchParams();
  if (params?.unread_only !== undefined) {
    searchParams.set('unread_only', String(params.unread_only));
  }
  if (params?.limit !== undefined) {
    searchParams.set('limit', String(params.limit));
  }
  const queryString = searchParams.toString();
  return fetchApi(`/notifications${queryString ? `?${queryString}` : ''}`, {}, true);
}

export async function getUnreadCount(): Promise<UnreadCount> {
  return fetchApi('/notifications/unread-count', {}, true);
}

export async function markNotificationRead(id: number): Promise<void> {
  await fetchApi(`/notifications/${id}/read`, {
    method: 'POST',
  }, true);
}

export async function markAllNotificationsRead(): Promise<{ marked_count: number }> {
  return fetchApi('/notifications/mark-all-read', {
    method: 'POST',
  }, true);
}

export async function deleteNotification(id: number): Promise<void> {
  await fetchApi(`/notifications/${id}`, {
    method: 'DELETE',
  }, true);
}
