'use client';

import { useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useSTT } from '@/lib/hooks/useSTT';
import { Mic, MicOff, Upload, Loader2, FileAudio } from 'lucide-react';

export function STTTab() {
  const {
    isLoading,
    isRecording,
    error,
    transcript,
    transcribeFile,
    startRecording,
    stopRecording,
  } = useSTT();

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        transcribeFile(file);
      }
    },
    [transcribeFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith('audio/')) {
        transcribeFile(file);
      }
    },
    [transcribeFile]
  );

  return (
    <div className="h-full flex gap-4">
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mic className="h-5 w-5 text-primary" />
            Speech to Text
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Upload zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors"
          >
            <FileAudio className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-muted-foreground mb-4">
              Drag and drop an audio file, or click to upload
            </p>
            <input
              type="file"
              accept="audio/*"
              onChange={handleFileUpload}
              className="hidden"
              id="audio-upload"
            />
            <label
              htmlFor="audio-upload"
              className="inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all h-10 px-4 py-2 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground cursor-pointer"
            >
              <Upload className="h-4 w-4 mr-2" />
              Choose File
            </label>
          </div>

          {/* Recording controls */}
          <div className="flex justify-center">
            <Button
              size="lg"
              variant={isRecording ? 'destructive' : 'default'}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isLoading}
              className="w-48"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Transcribing...
                </>
              ) : isRecording ? (
                <>
                  <MicOff className="h-4 w-4 mr-2" />
                  Stop Recording
                </>
              ) : (
                <>
                  <Mic className="h-4 w-4 mr-2" />
                  Start Recording
                </>
              )}
            </Button>
          </div>

          {isRecording && (
            <div className="flex justify-center">
              <div className="flex items-center gap-2 text-destructive">
                <div className="h-3 w-3 rounded-full bg-destructive animate-pulse" />
                Recording...
              </div>
            </div>
          )}

          {error && (
            <div className="text-destructive text-sm p-2 bg-destructive/10 rounded-lg">
              {error}
            </div>
          )}

          {/* Transcript */}
          {transcript && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">
                Transcript
              </h3>
              <div className="p-4 bg-secondary/50 rounded-lg border border-border">
                <p className="whitespace-pre-wrap">{transcript}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigator.clipboard.writeText(transcript)}
              >
                Copy to clipboard
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
