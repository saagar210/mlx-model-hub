'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { useTTS } from '@/lib/hooks/useTTS';
import { Volume2, Play, Pause, Square, Loader2 } from 'lucide-react';

export function TTSTab() {
  const [text, setText] = useState('');
  const [speed, setSpeed] = useState(1.0);

  const { isLoading, isPlaying, error, audioUrl, generate, play, pause, stop } =
    useTTS({ speed });

  const handleGenerate = () => {
    if (text.trim()) {
      generate(text);
    }
  };

  return (
    <div className="h-full flex gap-4">
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Volume2 className="h-5 w-5 text-primary" />
            Text to Speech
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Enter text to convert to speech..."
            className="min-h-[200px]"
          />

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>{text.length} characters</span>
            <span>{text.split(/\s+/).filter(Boolean).length} words</span>
          </div>

          <Slider
            label="Speed"
            value={speed}
            onChange={setSpeed}
            min={0.5}
            max={2.0}
            step={0.1}
          />

          {error && (
            <div className="text-destructive text-sm p-2 bg-destructive/10 rounded-lg">
              {error}
            </div>
          )}

          <div className="flex gap-2">
            <Button
              onClick={handleGenerate}
              disabled={!text.trim() || isLoading}
              className="flex-1"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Volume2 className="h-4 w-4 mr-2" />
                  Generate Speech
                </>
              )}
            </Button>

            {audioUrl && (
              <>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={isPlaying ? pause : play}
                >
                  {isPlaying ? (
                    <Pause className="h-4 w-4" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                </Button>
                <Button variant="outline" size="icon" onClick={stop}>
                  <Square className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>

          {audioUrl && (
            <div className="pt-4">
              <audio src={audioUrl} controls className="w-full" />
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
