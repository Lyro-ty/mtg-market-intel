/**
 * Moderation API functions for admin moderation dashboard.
 */
import { fetchApi } from './client';

// =============================================================================
// Types
// =============================================================================

export type FlagLevel = 'low' | 'medium' | 'high' | 'critical';
export type FlagType = 'report' | 'auto_flag' | 'dispute' | 'appeal';

export interface ModerationQueueItem {
  id: number;
  target_user_id: number;
  target_username: string;
  flag_level: FlagLevel;
  flag_type: FlagType;
  flag_reason: string;
  report_count: number;
  created_at: string;
}

export interface ModerationQueueResponse {
  items: ModerationQueueItem[];
  total: number;
  pending_count: number;
  high_priority_count: number;
}

export interface ModerationStats {
  pending: number;
  high_priority: number;
  resolved_today: number;
}

export interface ReportInfo {
  id: number;
  reporter_id: number;
  reporter_username: string;
  reason: string;
  details: string | null;
  created_at: string;
}

export interface AutoFlagInfo {
  id: number;
  flag_type: string;
  severity: string;
  reason: string;
  created_at: string;
}

export interface PreviousActionInfo {
  id: number;
  action_type: string;
  reason: string | null;
  moderator_username: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface ModNoteInfo {
  id: number;
  moderator_id: number;
  moderator_username: string;
  content: string;
  created_at: string;
}

export interface TradeStatsSummary {
  total_trades: number;
  completed_trades: number;
  cancelled_trades: number;
  disputed_trades: number;
  completion_rate: number;
}

export interface RecentTradeInfo {
  id: number;
  other_party_username: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface ReportedMessageInfo {
  id: number;
  content: string;
  recipient_username: string;
  sent_at: string;
}

export interface TargetUserInfo {
  id: number;
  username: string;
  display_name: string | null;
  email: string;
  avatar_url: string | null;
  created_at: string | null;
  is_active: boolean;
  is_verified: boolean;
}

export interface ModerationCaseDetail {
  id: number;
  target_user_id: number;
  target_user: TargetUserInfo;
  reports: ReportInfo[];
  auto_flags: AutoFlagInfo[];
  previous_actions: PreviousActionInfo[];
  mod_notes: ModNoteInfo[];
  trade_stats: TradeStatsSummary;
  recent_trades: RecentTradeInfo[];
  reported_messages: ReportedMessageInfo[];
}

export interface ModerationActionResponse {
  id: number;
  action_type: string;
  reason: string | null;
  duration_days: number | null;
  expires_at: string | null;
  created_at: string;
}

export interface AppealResponse {
  id: number;
  user_id: number;
  username: string;
  moderation_action: ModerationActionResponse;
  appeal_text: string;
  evidence_urls: string[];
  status: string;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface TradeDisputeResponse {
  id: number;
  trade_proposal_id: number | null;
  filed_by: number;
  filer_username: string;
  dispute_type: string;
  description: string | null;
  status: string;
  assigned_moderator_id: number | null;
  resolution: string | null;
  resolution_notes: string | null;
  evidence_snapshot: Record<string, unknown> | null;
  created_at: string;
  resolved_at: string | null;
}

// =============================================================================
// Request Types
// =============================================================================

export interface TakeActionRequest {
  action: 'dismiss' | 'warn' | 'restrict' | 'suspend' | 'ban' | 'escalate';
  reason: string;
  duration_days?: number;
  related_report_id?: number;
}

export interface ResolveAppealRequest {
  resolution: 'upheld' | 'reduced' | 'overturned';
  notes: string;
}

export interface ResolveDisputeRequest {
  resolution: 'buyer_wins' | 'seller_wins' | 'mutual_cancel' | 'inconclusive';
  notes: string;
}

export interface AddModNoteRequest {
  content: string;
}

export interface ModerationQueueParams {
  status?: 'pending' | 'resolved';
  priority?: FlagLevel;
  page?: number;
  limit?: number;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * Get the moderation queue with pending items.
 * Requires moderator or admin role.
 */
export async function getModerationQueue(
  params: ModerationQueueParams = {}
): Promise<ModerationQueueResponse> {
  const searchParams = new URLSearchParams();

  if (params.status) {
    searchParams.append('status', params.status);
  }
  if (params.priority) {
    searchParams.append('priority', params.priority);
  }
  if (params.page !== undefined) {
    searchParams.append('page', params.page.toString());
  }
  if (params.limit !== undefined) {
    searchParams.append('limit', params.limit.toString());
  }

  const queryString = searchParams.toString();
  const url = queryString
    ? `/admin/moderation/queue?${queryString}`
    : '/admin/moderation/queue';

  return fetchApi(url, {}, true);
}

/**
 * Get moderation stats summary.
 * Calculates from queue data.
 */
export async function getModerationStats(): Promise<ModerationStats> {
  const queue = await getModerationQueue({ limit: 1 });
  return {
    pending: queue.pending_count,
    high_priority: queue.high_priority_count,
    resolved_today: 0, // Would need separate endpoint for this
  };
}

/**
 * Get detailed case information for a user.
 * Requires moderator or admin role.
 */
export async function getCaseDetail(userId: number): Promise<ModerationCaseDetail> {
  return fetchApi(`/admin/moderation/users/${userId}`, {}, true);
}

/**
 * Take a moderation action against a user.
 * Requires moderator or admin role.
 */
export async function takeAction(
  userId: number,
  request: TakeActionRequest
): Promise<ModerationActionResponse> {
  return fetchApi(`/admin/moderation/users/${userId}/actions`, {
    method: 'POST',
    body: JSON.stringify(request),
  }, true);
}

/**
 * Get moderator notes for a user.
 * Requires moderator or admin role.
 */
export async function getUserNotes(userId: number): Promise<ModNoteInfo[]> {
  return fetchApi(`/admin/moderation/users/${userId}/notes`, {}, true);
}

/**
 * Add a moderator note about a user.
 * Requires moderator or admin role.
 */
export async function addUserNote(
  userId: number,
  request: AddModNoteRequest
): Promise<ModNoteInfo> {
  return fetchApi(`/admin/moderation/users/${userId}/notes`, {
    method: 'POST',
    body: JSON.stringify(request),
  }, true);
}

/**
 * Get list of appeals.
 * Requires moderator or admin role.
 */
export async function getAppeals(
  status?: string,
  page: number = 1,
  limit: number = 20
): Promise<AppealResponse[]> {
  const searchParams = new URLSearchParams();

  if (status) {
    searchParams.append('status', status);
  }
  searchParams.append('page', page.toString());
  searchParams.append('limit', limit.toString());

  return fetchApi(`/admin/moderation/appeals?${searchParams.toString()}`, {}, true);
}

/**
 * Get appeal details.
 * Requires moderator or admin role.
 */
export async function getAppeal(appealId: number): Promise<AppealResponse> {
  return fetchApi(`/admin/moderation/appeals/${appealId}`, {}, true);
}

/**
 * Resolve an appeal.
 * Requires moderator or admin role.
 */
export async function resolveAppeal(
  appealId: number,
  request: ResolveAppealRequest
): Promise<AppealResponse> {
  return fetchApi(`/admin/moderation/appeals/${appealId}/resolve`, {
    method: 'POST',
    body: JSON.stringify(request),
  }, true);
}

/**
 * Get list of trade disputes.
 * Requires moderator or admin role.
 */
export async function getDisputes(
  status?: string,
  page: number = 1,
  limit: number = 20
): Promise<TradeDisputeResponse[]> {
  const searchParams = new URLSearchParams();

  if (status) {
    searchParams.append('status', status);
  }
  searchParams.append('page', page.toString());
  searchParams.append('limit', limit.toString());

  return fetchApi(`/admin/moderation/disputes?${searchParams.toString()}`, {}, true);
}

/**
 * Get dispute details.
 * Requires moderator or admin role.
 */
export async function getDispute(disputeId: number): Promise<TradeDisputeResponse> {
  return fetchApi(`/admin/moderation/disputes/${disputeId}`, {}, true);
}

/**
 * Assign yourself to a dispute.
 * Requires moderator or admin role.
 */
export async function assignDispute(
  disputeId: number
): Promise<{ status: string; moderator_id: number }> {
  return fetchApi(`/admin/moderation/disputes/${disputeId}/assign`, {
    method: 'POST',
  }, true);
}

/**
 * Resolve a trade dispute.
 * Requires moderator or admin role.
 */
export async function resolveDispute(
  disputeId: number,
  request: ResolveDisputeRequest
): Promise<TradeDisputeResponse> {
  return fetchApi(`/admin/moderation/disputes/${disputeId}/resolve`, {
    method: 'POST',
    body: JSON.stringify(request),
  }, true);
}
