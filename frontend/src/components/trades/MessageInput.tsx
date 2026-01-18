'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import Image from 'next/image';
import { Send, ImagePlus, CreditCard, X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CardEmbedPicker } from './CardEmbedPicker';

interface SelectedCard {
  id: number;
  name: string;
  set_code?: string;
  image_url?: string;
}

interface MessageInputProps {
  onSend: (content?: string, cardId?: number, file?: File) => void;
  isLoading?: boolean;
  tradeId: number;
  disabled?: boolean;
  placeholder?: string;
}

const MAX_CHARACTERS = 2000;
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

/**
 * Message input component with text input, photo upload, and card embed support.
 */
export function MessageInput({
  onSend,
  isLoading = false,
  tradeId,
  disabled = false,
  placeholder = 'Type a message...',
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [selectedCard, setSelectedCard] = useState<SelectedCard | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [showCardPicker, setShowCardPicker] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
    }
  }, []);

  useEffect(() => {
    adjustTextareaHeight();
  }, [content, adjustTextareaHeight]);

  // Generate file preview URL
  useEffect(() => {
    if (selectedFile) {
      const url = URL.createObjectURL(selectedFile);
      setFilePreview(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setFilePreview(null);
    }
  }, [selectedFile]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setFileError(null);

    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        setFileError('Please select an image file');
        return;
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        setFileError('Image must be under 5MB');
        return;
      }

      setSelectedFile(file);
    }

    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleCardSelect = (card: SelectedCard) => {
    setSelectedCard(card);
    setShowCardPicker(false);
  };

  const handleRemoveCard = () => {
    setSelectedCard(null);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setFilePreview(null);
    setFileError(null);
  };

  const handleSend = () => {
    const trimmedContent = content.trim();

    // Need at least content, card, or file
    if (!trimmedContent && !selectedCard && !selectedFile) {
      return;
    }

    onSend(
      trimmedContent || undefined,
      selectedCard?.id,
      selectedFile || undefined
    );

    // Reset state
    setContent('');
    setSelectedCard(null);
    setSelectedFile(null);
    setFilePreview(null);

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const charactersRemaining = MAX_CHARACTERS - content.length;
  const isOverLimit = charactersRemaining < 0;
  const canSend = !isLoading && !disabled && !isOverLimit && (content.trim() || selectedCard || selectedFile);

  return (
    <div className="border-t border-[rgb(var(--border))] bg-[rgb(var(--card))] p-4">
      {/* Previews */}
      {(selectedCard || filePreview) && (
        <div className="flex flex-wrap gap-2 mb-3">
          {/* Card preview */}
          {selectedCard && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[rgb(var(--secondary))] border border-[rgb(var(--border))]">
              {selectedCard.image_url ? (
                <Image
                  src={selectedCard.image_url}
                  alt={selectedCard.name}
                  width={32}
                  height={45}
                  className="rounded object-cover"
                  unoptimized
                />
              ) : (
                <div className="w-8 h-11 rounded bg-gradient-to-br from-amber-900/40 to-amber-700/20 flex items-center justify-center">
                  <span className="text-[8px] text-amber-500/60">MTG</span>
                </div>
              )}
              <div className="min-w-0">
                <div className="text-sm font-medium text-[rgb(var(--foreground))] line-clamp-1">
                  {selectedCard.name}
                </div>
                {selectedCard.set_code && (
                  <div className="text-xs text-[rgb(var(--muted-foreground))] uppercase">
                    {selectedCard.set_code}
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 ml-1"
                onClick={handleRemoveCard}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          )}

          {/* File preview */}
          {filePreview && (
            <div className="relative">
              <Image
                src={filePreview}
                alt="Upload preview"
                width={80}
                height={80}
                className="rounded-lg object-cover w-20 h-20 border border-[rgb(var(--border))]"
                unoptimized
              />
              <Button
                variant="ghost"
                size="sm"
                className="absolute -top-2 -right-2 h-6 w-6 p-0 rounded-full bg-[rgb(var(--background))] border border-[rgb(var(--border))] hover:bg-red-500/10 hover:text-red-500"
                onClick={handleRemoveFile}
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* File error */}
      {fileError && (
        <div className="mb-2 text-sm text-red-500">
          {fileError}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        {/* Action buttons */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Photo upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <Button
            variant="ghost"
            size="sm"
            className="h-9 w-9 p-0"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || !!selectedFile}
            title="Upload image"
          >
            <ImagePlus className="w-5 h-5" />
          </Button>

          {/* Card embed */}
          <Button
            variant="ghost"
            size="sm"
            className="h-9 w-9 p-0"
            onClick={() => setShowCardPicker(true)}
            disabled={disabled || !!selectedCard}
            title="Embed card"
          >
            <CreditCard className="w-5 h-5" />
          </Button>
        </div>

        {/* Text input */}
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            rows={1}
            className={cn(
              'w-full resize-none rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-3 py-2 text-sm',
              'placeholder:text-[rgb(var(--muted-foreground))]',
              'focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500/50',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              isOverLimit && 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
            )}
          />

          {/* Character count */}
          {content.length > MAX_CHARACTERS - 200 && (
            <div
              className={cn(
                'absolute right-2 bottom-2 text-xs',
                isOverLimit ? 'text-red-500' : 'text-[rgb(var(--muted-foreground))]'
              )}
            >
              {charactersRemaining}
            </div>
          )}
        </div>

        {/* Send button */}
        <Button
          variant="primary"
          size="sm"
          className="h-9 w-9 p-0 shrink-0"
          onClick={handleSend}
          disabled={!canSend}
          title="Send message"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </Button>
      </div>

      {/* Card picker dialog */}
      <CardEmbedPicker
        open={showCardPicker}
        onOpenChange={setShowCardPicker}
        onSelect={handleCardSelect}
      />
    </div>
  );
}
