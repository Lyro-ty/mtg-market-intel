'use client';

import { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Trash2, ThumbsUp, AlertCircle } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from '@/components/ui/dialog';
import { formatCurrency, formatRelativeTime, cn } from '@/lib/utils';
import type { TradeThreadMessage } from '@/lib/api/trade-threads';

interface TradeMessageProps {
  message: TradeThreadMessage;
  isOwn: boolean;
  currentUserId: number;
  onReact?: (messageId: number, reactionType: string) => void;
  onDelete?: (messageId: number) => void;
}

/**
 * Get initials from username or display name
 */
function getInitials(username: string, displayName?: string): string {
  const name = displayName ?? username;
  const parts = name.split(/[\s_-]+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

/**
 * Available reaction types with their display emojis
 */
const REACTIONS: Record<string, string> = {
  thumbs_up: '👍',
  thumbs_down: '👎',
  heart: '❤️',
  fire: '🔥',
  check: '✅',
};

/**
 * Individual message component for trade thread chat.
 * Displays sender info, message content, card embeds, photo attachments, and reactions.
 */
export function TradeMessage({
  message,
  isOwn,
  currentUserId,
  onReact,
  onDelete,
}: TradeMessageProps) {
  const [showImageModal, setShowImageModal] = useState<string | null>(null);

  // Check if message is deleted
  if (message.deleted_at) {
    return (
      <div
        className={cn(
          'flex gap-3',
          isOwn ? 'flex-row-reverse' : 'flex-row'
        )}
      >
        <div className="w-8 h-8 shrink-0" /> {/* Avatar placeholder */}
        <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[rgb(var(--muted))]/30 text-[rgb(var(--muted-foreground))] italic">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">This message was deleted</span>
        </div>
      </div>
    );
  }

  // Check if current user has reacted with each type
  const userReactions = new Set<string>();
  Object.entries(message.reactions).forEach(([type, userIds]) => {
    if (userIds.includes(currentUserId)) {
      userReactions.add(type);
    }
  });

  return (
    <div
      className={cn(
        'flex gap-3 group',
        isOwn ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <Avatar className="h-8 w-8 shrink-0">
        {message.sender_avatar_url ? (
          <AvatarImage src={message.sender_avatar_url} alt={message.sender_username} />
        ) : null}
        <AvatarFallback
          className={cn(
            'text-xs font-medium',
            isOwn
              ? 'bg-amber-500/20 text-amber-500'
              : 'bg-blue-500/20 text-blue-500'
          )}
        >
          {getInitials(message.sender_username, message.sender_display_name)}
        </AvatarFallback>
      </Avatar>

      {/* Message Content */}
      <div className={cn('flex flex-col max-w-[70%]', isOwn ? 'items-end' : 'items-start')}>
        {/* Sender name and time */}
        <div
          className={cn(
            'flex items-center gap-2 mb-1',
            isOwn ? 'flex-row-reverse' : 'flex-row'
          )}
        >
          <span className="text-xs font-medium text-[rgb(var(--foreground))]">
            {isOwn ? 'You' : message.sender_display_name ?? message.sender_username}
          </span>
          <span className="text-xs text-[rgb(var(--muted-foreground))]">
            {formatRelativeTime(message.created_at)}
          </span>
        </div>

        {/* System message styling */}
        {message.is_system_message ? (
          <div className="px-3 py-2 rounded-lg bg-[rgb(var(--secondary))]/50 border border-[rgb(var(--border))]">
            <p className="text-sm text-[rgb(var(--muted-foreground))] italic">
              {message.content}
            </p>
          </div>
        ) : (
          <>
            {/* Message bubble */}
            {message.content && (
              <div
                className={cn(
                  'px-4 py-2 rounded-2xl',
                  isOwn
                    ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white rounded-br-sm'
                    : 'bg-[rgb(var(--secondary))] text-[rgb(var(--foreground))] rounded-bl-sm'
                )}
              >
                <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
              </div>
            )}

            {/* Card embed */}
            {message.card && (
              <Link
                href={`/cards/${message.card.id}`}
                className={cn(
                  'mt-2 flex items-center gap-3 p-3 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--card))] hover:border-amber-500/50 transition-colors',
                  'max-w-[280px]'
                )}
              >
                {message.card.image_url ? (
                  <Image
                    src={message.card.image_url}
                    alt={message.card.name}
                    width={48}
                    height={67}
                    className="rounded object-cover shrink-0"
                    unoptimized
                  />
                ) : (
                  <div className="w-12 h-[67px] rounded bg-gradient-to-br from-amber-900/40 to-amber-700/20 flex items-center justify-center shrink-0">
                    <span className="text-[8px] text-amber-500/60 font-medium">MTG</span>
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[rgb(var(--foreground))] line-clamp-1">
                    {message.card.name}
                  </div>
                  {message.card.set_code && (
                    <div className="text-xs text-[rgb(var(--muted-foreground))] uppercase">
                      {message.card.set_code}
                    </div>
                  )}
                  {message.card.price !== undefined && message.card.price !== null && (
                    <div className="text-sm font-semibold text-amber-500 mt-1">
                      {formatCurrency(message.card.price)}
                    </div>
                  )}
                </div>
              </Link>
            )}

            {/* Photo attachments */}
            {message.has_attachments && message.attachments.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {message.attachments.map((attachment) => (
                  <Dialog key={attachment.id}>
                    <DialogTrigger asChild>
                      <button
                        onClick={() => setShowImageModal(attachment.file_url)}
                        className="relative rounded-lg overflow-hidden border border-[rgb(var(--border))] hover:border-amber-500/50 transition-colors"
                      >
                        <Image
                          src={attachment.file_url}
                          alt="Attachment"
                          width={120}
                          height={120}
                          className="object-cover w-[120px] h-[120px]"
                          unoptimized
                        />
                      </button>
                    </DialogTrigger>
                    <DialogContent className="max-w-3xl p-0 overflow-hidden bg-transparent border-none">
                      <Image
                        src={attachment.file_url}
                        alt="Attachment"
                        width={800}
                        height={800}
                        className="object-contain max-h-[80vh] w-auto mx-auto"
                        unoptimized
                      />
                    </DialogContent>
                  </Dialog>
                ))}
              </div>
            )}
          </>
        )}

        {/* Reactions display */}
        {Object.keys(message.reactions).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {Object.entries(message.reactions).map(([type, userIds]) => {
              if (userIds.length === 0) return null;
              const hasReacted = userIds.includes(currentUserId);
              return (
                <button
                  key={type}
                  onClick={() => onReact?.(message.id, type)}
                  className={cn(
                    'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs transition-colors',
                    hasReacted
                      ? 'bg-amber-500/20 border border-amber-500/50'
                      : 'bg-[rgb(var(--secondary))] border border-transparent hover:border-[rgb(var(--border))]'
                  )}
                >
                  <span>{REACTIONS[type] || type}</span>
                  <span className="text-[rgb(var(--muted-foreground))]">{userIds.length}</span>
                </button>
              );
            })}
          </div>
        )}

        {/* Action buttons (visible on hover for own messages) */}
        {!message.is_system_message && (
          <div
            className={cn(
              'flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity',
              isOwn ? 'flex-row-reverse' : 'flex-row'
            )}
          >
            {/* Quick reaction button */}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0"
              onClick={() => onReact?.(message.id, 'thumbs_up')}
              title="Like"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </Button>

            {/* Delete button (only for own messages) */}
            {isOwn && onDelete && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-red-500 hover:text-red-600 hover:bg-red-500/10"
                onClick={() => onDelete(message.id)}
                title="Delete message"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
