'use client';

import { useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Eye, Upload, Loader2, ImageIcon } from 'lucide-react';
import { analyzeImage } from '@/lib/api';

export function VisionTab() {
  const [image, setImage] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('What do you see in this image?');
  const [response, setResponse] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setImageFile(file);
        const reader = new FileReader();
        reader.onload = (e) => {
          setImage(e.target?.result as string);
          setResponse(null);
        };
        reader.readAsDataURL(file);
      }
    },
    []
  );

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setImage(e.target?.result as string);
        setResponse(null);
      };
      reader.readAsDataURL(file);
    }
  }, []);

  const handleAnalyze = async () => {
    if (!imageFile || !prompt.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await analyzeImage(imageFile, prompt);
      setResponse(result.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-full flex gap-4">
      <Card className="flex-1">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-primary" />
            Vision Analysis
          </CardTitle>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Image upload/display */}
          {image ? (
            <div className="relative">
              <img
                src={image}
                alt="Uploaded"
                className="w-full max-h-[300px] object-contain rounded-lg border border-border"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setImage(null);
                  setImageFile(null);
                  setResponse(null);
                }}
                className="absolute top-2 right-2"
              >
                Remove
              </Button>
            </div>
          ) : (
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-primary/50 transition-colors"
            >
              <ImageIcon className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground mb-4">
                Drag and drop an image, or click to upload
              </p>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
                id="image-upload"
              />
              <label
                htmlFor="image-upload"
                className="inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all h-10 px-4 py-2 border border-input bg-transparent shadow-sm hover:bg-accent hover:text-accent-foreground cursor-pointer"
              >
                <Upload className="h-4 w-4 mr-2" />
                Choose Image
              </label>
            </div>
          )}

          {/* Prompt input */}
          <Textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Ask a question about the image..."
            className="min-h-[80px]"
          />

          {error && (
            <div className="text-destructive text-sm p-2 bg-destructive/10 rounded-lg">
              {error}
            </div>
          )}

          <Button
            onClick={handleAnalyze}
            disabled={!imageFile || !prompt.trim() || isLoading}
            className="w-full"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Eye className="h-4 w-4 mr-2" />
                Analyze Image
              </>
            )}
          </Button>

          {/* Response */}
          {response && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">
                Analysis
              </h3>
              <div className="p-4 bg-secondary/50 rounded-lg border border-border">
                <p className="whitespace-pre-wrap">{response}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
