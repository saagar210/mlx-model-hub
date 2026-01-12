'use client';

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { useChat } from '@/lib/hooks/useChat';
import { Trash2, Settings2, MessageSquare } from 'lucide-react';

const TEXT_MODELS = [
  'mlx-community/Qwen2.5-7B-Instruct-4bit',
  'mlx-community/Qwen2.5-3B-Instruct-4bit',
  'mlx-community/Qwen2.5-1.5B-Instruct-4bit',
];

export function ChatTab() {
  const [model, setModel] = useState(TEXT_MODELS[0]);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(2048);
  const [showSettings, setShowSettings] = useState(false);

  const {
    messages,
    input,
    setInput,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    stopGeneration,
  } = useChat({ model, temperature, maxTokens });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="h-full flex gap-4">
      {/* Main chat area */}
      <Card className="flex-1 flex flex-col">
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-primary" />
            Chat
          </CardTitle>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowSettings(!showSettings)}
            >
              <Settings2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={clearMessages}
              disabled={messages.length === 0}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <MessageSquare className="h-12 w-12 mb-4 opacity-20" />
                <p>Start a conversation</p>
              </div>
            ) : (
              messages.map((msg, i) => <ChatMessage key={i} message={msg} />)
            )}
            {isLoading && messages[messages.length - 1]?.role === 'assistant' && (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <div className="animate-pulse-subtle">Generating...</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error display */}
          {error && (
            <div className="text-destructive text-sm mb-2 p-2 bg-destructive/10 rounded-lg">
              {error}
            </div>
          )}

          {/* Input */}
          <ChatInput
            value={input}
            onChange={setInput}
            onSend={sendMessage}
            onStop={stopGeneration}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>

      {/* Settings panel */}
      {showSettings && (
        <Card className="w-72 shrink-0">
          <CardHeader>
            <CardTitle className="text-sm">Settings</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground">Model</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full h-10 rounded-lg border border-input bg-secondary/50 px-3 text-sm"
              >
                {TEXT_MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m.split('/')[1]}
                  </option>
                ))}
              </select>
            </div>

            <Slider
              label="Temperature"
              value={temperature}
              onChange={setTemperature}
              min={0}
              max={2}
              step={0.1}
            />

            <Slider
              label="Max Tokens"
              value={maxTokens}
              onChange={setMaxTokens}
              min={256}
              max={8192}
              step={256}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
