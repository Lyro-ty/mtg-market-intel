/**
 * Connections API functions for user-to-user connections.
 */
import { fetchApi } from './client';

export interface ConnectionRequestorInfo {
  id: number;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  location: string | null;
}

export interface ConnectionRequest {
  id: number;
  requester_id: number;
  recipient_id: number;
  card_ids: number[] | null;
  message: string | null;
  status: 'pending' | 'accepted' | 'declined';
  expires_at: string;
  responded_at: string | null;
  created_at: string;
  requester?: ConnectionRequestorInfo;
  recipient?: ConnectionRequestorInfo;
}

export interface ConnectionRequestListResponse {
  requests: ConnectionRequest[];
  total: number;
}

export interface SendConnectionRequestData {
  recipient_id: number;
  card_ids?: number[];
  message?: string;
}

/**
 * Send a connection request to another user.
 */
export async function sendConnectionRequest(
  data: SendConnectionRequestData
): Promise<ConnectionRequest> {
  return fetchApi('/connections/request', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Get pending connection requests for the current user.
 */
export async function getPendingRequests(
  type: 'received' | 'sent' = 'received'
): Promise<ConnectionRequestListResponse> {
  return fetchApi(`/connections/pending?type=${type}`);
}

/**
 * Accept a connection request.
 */
export async function acceptConnectionRequest(
  requestId: number
): Promise<{ status: string; message: string }> {
  return fetchApi(`/connections/${requestId}/accept`, {
    method: 'POST',
  });
}

/**
 * Decline a connection request.
 */
export async function declineConnectionRequest(
  requestId: number
): Promise<{ status: string; message: string }> {
  return fetchApi(`/connections/${requestId}/decline`, {
    method: 'POST',
  });
}

/**
 * Cancel a pending connection request you sent.
 */
export async function cancelConnectionRequest(
  requestId: number
): Promise<{ status: string; message: string }> {
  return fetchApi(`/connections/${requestId}/cancel`, {
    method: 'DELETE',
  });
}

/**
 * Get list of connected users.
 */
export async function getConnections(
  limit: number = 50,
  offset: number = 0
): Promise<{ connections: ConnectionRequestorInfo[]; total: number }> {
  return fetchApi(`/connections?limit=${limit}&offset=${offset}`);
}

/**
 * Remove a connection.
 */
export async function removeConnection(
  userId: number
): Promise<{ status: string; message: string }> {
  return fetchApi(`/connections/${userId}`, {
    method: 'DELETE',
  });
}

/**
 * Check connection status with a user.
 */
export async function checkConnectionStatus(
  userId: number
): Promise<{
  connected: boolean;
  pending_sent: boolean;
  pending_received: boolean;
}> {
  return fetchApi(`/connections/status/${userId}`);
}
