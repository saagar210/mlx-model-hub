'use client';

import { cn } from '@/lib/utils';
import { User, Bot } from 'lucide-react';
import type { Message } from '@/types/api';

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex gap-3 p-4 rounded-lg',
        isUser ? 'message-user' : 'message-assistant'
      )}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary/20' : 'bg-accent/20'
        )}
      >
        {isUser ? (
          <User className="h-4 w-4 text-primary" />
        ) : (
          <Bot className="h-4 w-4 text-accent" />
        )}
      </div>
      <div className="flex-1 space-y-2 overflow-hidden">
        <p className="text-xs font-medium text-muted-foreground">
          {isUser ? 'You' : 'AI'}
        </p>
        <div className="prose prose-invert prose-sm max-w-none">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        </div>
      </div>
    </div>
  );
}
