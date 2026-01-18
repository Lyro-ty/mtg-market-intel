'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronUp, Clock, ArrowLeftRight, Loader2 } from 'lucide-react';
import { TradeMessage } from './TradeMessage';
import { MessageInput } from './MessageInput';
import { TradeStatusBadge } from './TradeStatusBadge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { formatCurrency, cn } from '@/lib/utils';
import {
  getTradeThread,
  getThreadSummary,
  sendMessage,
  uploadAttachment,
  toggleReaction,
  deleteMessage,
  type TradeThread as TradeThreadType,
  type TradeThreadSummary,
} from '@/lib/api/trade-threads';

interface TradeThreadProps {
  tradeId: number;
  currentUserId: number;
}

/**
 * Format expiration time for display
 */
function formatExpiration(expiresAt: string): string {
  const expDate = new Date(expiresAt);
  const now = new Date();
  const diffMs = expDate.getTime() - now.getTime();

  if (diffMs <= 0) {
    return 'Expired';
  }

  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffDays > 0) {
    return `${diffDays}d left`;
  }
  if (diffHours > 0) {
    return `${diffHours}h left`;
  }
  return 'Expiring soon';
}

/**
 * Main trade chat component.
 * Displays trade summary header, scrollable message list, and message input.
 */
export function TradeThread({ tradeId, currentUserId }: TradeThreadProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const [showLoadMore, setShowLoadMore] = useState(false);

  // Fetch thread data
  const {
    data: thread,
    isLoading: threadLoading,
    error: threadError,
  } = useQuery({
    queryKey: ['trade-thread', tradeId],
    queryFn: () => getTradeThread(tradeId),
    refetchInterval: 30000, // Poll every 30 seconds
  });

  // Fetch trade summary
  const {
    data: summary,
    isLoading: summaryLoading,
  } = useQuery({
    queryKey: ['trade-summary', tradeId],
    queryFn: () => getThreadSummary(tradeId),
  });

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: async (data: { content?: string; cardId?: number; file?: File }) => {
      // First send the message
      const message = await sendMessage(tradeId, {
        content: data.content,
        card_id: data.cardId,
      });

      // If there's a file, upload it as attachment
      if (data.file) {
        await uploadAttachment(tradeId, message.id, data.file);
      }

      return message;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-thread', tradeId] });
    },
  });

  // Toggle reaction mutation
  const reactionMutation = useMutation({
    mutationFn: ({ messageId, reactionType }: { messageId: number; reactionType: string }) =>
      toggleReaction(tradeId, messageId, reactionType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-thread', tradeId] });
    },
  });

  // Delete message mutation
  const deleteMutation = useMutation({
    mutationFn: (messageId: number) => deleteMessage(tradeId, messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-thread', tradeId] });
    },
  });

  // Auto-scroll to bottom on new messages
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  useEffect(() => {
    if (thread?.messages) {
      scrollToBottom();
    }
  }, [thread?.messages?.length, scrollToBottom]);

  // Handle send message
  const handleSend = (content?: string, cardId?: number, file?: File) => {
    sendMutation.mutate({ content, cardId, file });
  };

  // Handle reaction toggle
  const handleReact = (messageId: number, reactionType: string) => {
    reactionMutation.mutate({ messageId, reactionType });
  };

  // Handle delete message
  const handleDelete = (messageId: number) => {
    if (window.confirm('Delete this message?')) {
      deleteMutation.mutate(messageId);
    }
  };

  // Check if trade is still active for messaging
  const isActiveStatus = summary && ['pending', 'accepted', 'countered'].includes(summary.status);

  if (threadLoading || summaryLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
      </div>
    );
  }

  if (threadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 p-4 text-center">
        <p className="text-red-500">Failed to load chat</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => queryClient.invalidateQueries({ queryKey: ['trade-thread', tradeId] })}
        >
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[rgb(var(--background))]">
      {/* Header with trade summary */}
      <div className="shrink-0 border-b border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4">
        {summary && (
          <>
            {/* Status and expiration */}
            <div className="flex items-center justify-between mb-3">
              <TradeStatusBadge status={summary.status} />
              {summary.expires_at && summary.status === 'pending' && (
                <div className="flex items-center gap-1 text-xs text-[rgb(var(--muted-foreground))]">
                  <Clock className="w-3 h-3" />
                  <span>{formatExpiration(summary.expires_at)}</span>
                </div>
              )}
            </div>

            {/* Trade values */}
            <div className="flex items-center justify-between gap-4">
              {/* Offering side */}
              <div className="flex-1 text-center">
                <div className="text-xs text-[rgb(var(--muted-foreground))] mb-1">
                  {summary.proposer_username} offers
                </div>
                <div className="text-sm font-medium text-[rgb(var(--foreground))]">
                  {summary.offer_card_count} card{summary.offer_card_count !== 1 ? 's' : ''}
                </div>
                <div className="text-lg font-semibold text-amber-500">
                  {formatCurrency(summary.offer_value)}
                </div>
              </div>

              {/* Exchange icon */}
              <div className="shrink-0">
                <ArrowLeftRight className="w-5 h-5 text-[rgb(var(--muted-foreground))]" />
              </div>

              {/* Requesting side */}
              <div className="flex-1 text-center">
                <div className="text-xs text-[rgb(var(--muted-foreground))] mb-1">
                  {summary.recipient_username} offers
                </div>
                <div className="text-sm font-medium text-[rgb(var(--foreground))]">
                  {summary.request_card_count} card{summary.request_card_count !== 1 ? 's' : ''}
                </div>
                <div className="text-lg font-semibold text-amber-500">
                  {formatCurrency(summary.request_value)}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-hidden relative">
        <ScrollArea ref={scrollAreaRef} className="h-full">
          <div className="p-4 space-y-4">
            {/* Load more button */}
            {showLoadMore && (
              <div className="flex justify-center">
                <Button variant="ghost" size="sm" className="gap-1">
                  <ChevronUp className="w-4 h-4" />
                  Load earlier messages
                </Button>
              </div>
            )}

            {/* Messages */}
            {thread?.messages && thread.messages.length > 0 ? (
              thread.messages.map((message) => (
                <TradeMessage
                  key={message.id}
                  message={message}
                  isOwn={message.sender_id === currentUserId}
                  currentUserId={currentUserId}
                  onReact={handleReact}
                  onDelete={handleDelete}
                />
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <p className="text-[rgb(var(--muted-foreground))]">
                  No messages yet
                </p>
                <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1">
                  Start the conversation about this trade
                </p>
              </div>
            )}

            {/* Scroll anchor */}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
      </div>

      {/* Message input */}
      {isActiveStatus ? (
        <MessageInput
          tradeId={tradeId}
          onSend={handleSend}
          isLoading={sendMutation.isPending}
          placeholder="Type a message about this trade..."
        />
      ) : (
        <div className="shrink-0 border-t border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4 text-center">
          <p className="text-sm text-[rgb(var(--muted-foreground))]">
            This trade is {summary?.status}. Messaging is disabled.
          </p>
        </div>
      )}
    </div>
  );
}
