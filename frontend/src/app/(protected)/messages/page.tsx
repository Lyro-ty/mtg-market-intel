'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle,
  Send,
  Loader2,
  User,
  ArrowLeft,
  Check,
  CheckCheck,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ornate/page-header';
import { cn, formatRelativeTime } from '@/lib/utils';
import {
  getConversations,
  getConversation,
  sendMessage,
  ApiError,
} from '@/lib/api';
import type { ConversationSummary, Message } from '@/lib/api/messages';
import { useAuth } from '@/contexts/AuthContext';

interface ConversationListProps {
  conversations: ConversationSummary[];
  selectedUserId: number | null;
  onSelect: (userId: number) => void;
  isLoading: boolean;
}

function ConversationList({
  conversations,
  selectedUserId,
  onSelect,
  isLoading,
}: ConversationListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-6 h-6 animate-spin text-[rgb(var(--accent))]" />
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="p-6 text-center">
        <MessageCircle className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
        <p className="text-muted-foreground text-sm">No conversations yet</p>
        <p className="text-muted-foreground text-xs mt-1">
          Connect with other collectors to start messaging
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {conversations.map((conv) => (
        <button
          key={conv.user_id}
          className={cn(
            'w-full p-4 text-left hover:bg-secondary/50 transition-colors',
            selectedUserId === conv.user_id && 'bg-secondary'
          )}
          onClick={() => onSelect(conv.user_id)}
        >
          <div className="flex items-start gap-3">
            {/* Avatar */}
            <div className="w-10 h-10 rounded-full bg-[rgb(var(--accent))]/20 flex items-center justify-center shrink-0">
              {conv.avatar_url ? (
                <img
                  src={conv.avatar_url}
                  alt={conv.username}
                  className="w-10 h-10 rounded-full object-cover"
                />
              ) : (
                <User className="w-5 h-5 text-[rgb(var(--accent))]" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-foreground truncate">
                  {conv.display_name || conv.username}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatRelativeTime(conv.last_message_at)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-0.5">
                <p className="text-sm text-muted-foreground truncate">
                  {conv.last_message}
                </p>
                {conv.unread_count > 0 && (
                  <span className="shrink-0 w-5 h-5 rounded-full bg-[rgb(var(--accent))] text-white text-xs flex items-center justify-center">
                    {conv.unread_count > 9 ? '9+' : conv.unread_count}
                  </span>
                )}
              </div>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

interface ChatViewProps {
  userId: number;
  username: string;
  displayName: string | null;
  avatarUrl: string | null;
  onBack: () => void;
}

function ChatView({ userId, username, displayName, avatarUrl, onBack }: ChatViewProps) {
  const { user: currentUser } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchMessages = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getConversation(userId);
      // Messages come in reverse chronological order, so reverse them
      setMessages(response.messages.reverse());
      setHasMore(response.has_more);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load messages');
      }
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  useEffect(() => {
    if (!isLoading && messages.length > 0) {
      scrollToBottom();
    }
  }, [isLoading, messages.length]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [userId]);

  const handleSend = async () => {
    if (!newMessage.trim() || isSending) return;

    const content = newMessage.trim();
    setNewMessage('');
    setIsSending(true);
    setError(null);

    try {
      const sentMessage = await sendMessage({
        recipient_id: userId,
        content,
      });
      setMessages((prev) => [...prev, sentMessage]);
      scrollToBottom();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to send message');
      }
      setNewMessage(content); // Restore message on error
    } finally {
      setIsSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="lg:hidden"
          onClick={onBack}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="w-10 h-10 rounded-full bg-[rgb(var(--accent))]/20 flex items-center justify-center">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt={username}
              className="w-10 h-10 rounded-full object-cover"
            />
          ) : (
            <User className="w-5 h-5 text-[rgb(var(--accent))]" />
          )}
        </div>
        <div>
          <h3 className="font-medium text-foreground">{displayName || username}</h3>
          <p className="text-xs text-muted-foreground">@{username}</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-[rgb(var(--accent))]" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center">
            <div>
              <MessageCircle className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">No messages yet</p>
              <p className="text-sm text-muted-foreground">
                Start the conversation!
              </p>
            </div>
          </div>
        ) : (
          <>
            {hasMore && (
              <div className="text-center">
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Load earlier messages
                </Button>
              </div>
            )}
            {messages.map((message) => {
              const isOwn = message.sender_id === currentUser?.id;
              return (
                <div
                  key={message.id}
                  className={cn(
                    'flex',
                    isOwn ? 'justify-end' : 'justify-start'
                  )}
                >
                  <div
                    className={cn(
                      'max-w-[70%] rounded-2xl px-4 py-2',
                      isOwn
                        ? 'bg-[rgb(var(--accent))] text-white rounded-br-md'
                        : 'bg-secondary text-foreground rounded-bl-md'
                    )}
                  >
                    <p className="text-sm whitespace-pre-wrap break-words">
                      {message.content}
                    </p>
                    <div
                      className={cn(
                        'flex items-center gap-1 mt-1',
                        isOwn ? 'justify-end' : 'justify-start'
                      )}
                    >
                      <span
                        className={cn(
                          'text-xs',
                          isOwn ? 'text-white/70' : 'text-muted-foreground'
                        )}
                      >
                        {new Date(message.created_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      {isOwn && (
                        message.read_at ? (
                          <CheckCheck className="w-3 h-3 text-white/70" />
                        ) : (
                          <Check className="w-3 h-3 text-white/70" />
                        )
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 bg-[rgb(var(--destructive))]/10 border-t border-[rgb(var(--destructive))]/20">
          <p className="text-sm text-[rgb(var(--destructive))]">{error}</p>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2">
          <Input
            ref={inputRef}
            placeholder="Type a message..."
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            className="flex-1"
          />
          <Button
            className="gradient-arcane text-white shrink-0"
            onClick={handleSend}
            disabled={!newMessage.trim() || isSending}
          >
            {isSending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function MessagesPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<ConversationSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchConversations = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getConversations();
      setConversations(response.conversations);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to load conversations');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleSelectConversation = (userId: number) => {
    const conv = conversations.find((c) => c.user_id === userId);
    if (conv) {
      setSelectedConversation(conv);
    }
  };

  const handleBack = () => {
    setSelectedConversation(null);
    // Refresh conversations to update unread counts
    fetchConversations();
  };

  return (
    <div className="space-y-6 animate-in">
      <PageHeader
        title="Messages"
        subtitle="Chat with your connections"
      />

      {error && (
        <div className="p-4 rounded-lg bg-[rgb(var(--destructive))]/10 border border-[rgb(var(--destructive))]/20">
          <p className="text-[rgb(var(--destructive))]">{error}</p>
        </div>
      )}

      <Card className="glow-accent overflow-hidden">
        <div className="flex h-[calc(100vh-300px)] min-h-[500px]">
          {/* Conversation List */}
          <div
            className={cn(
              'w-full lg:w-80 border-r border-border overflow-y-auto',
              selectedConversation && 'hidden lg:block'
            )}
          >
            <div className="p-4 border-b border-border">
              <h2 className="font-heading text-lg text-foreground">Conversations</h2>
            </div>
            <ConversationList
              conversations={conversations}
              selectedUserId={selectedConversation?.user_id ?? null}
              onSelect={handleSelectConversation}
              isLoading={isLoading}
            />
          </div>

          {/* Chat View */}
          <div
            className={cn(
              'flex-1',
              !selectedConversation && 'hidden lg:flex'
            )}
          >
            {selectedConversation ? (
              <ChatView
                userId={selectedConversation.user_id}
                username={selectedConversation.username}
                displayName={selectedConversation.display_name}
                avatarUrl={selectedConversation.avatar_url}
                onBack={handleBack}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-center p-8">
                <div>
                  <MessageCircle className="w-16 h-16 mx-auto text-muted-foreground mb-4" />
                  <h3 className="text-lg font-medium text-foreground mb-2">
                    Select a conversation
                  </h3>
                  <p className="text-muted-foreground">
                    Choose a conversation from the list to start messaging
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
