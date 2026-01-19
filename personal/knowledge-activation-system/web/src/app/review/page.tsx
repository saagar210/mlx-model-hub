"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Eye,
  RotateCcw,
  Pause,
  CheckCircle2,
  TrendingUp,
  Zap,
  Keyboard,
  Clock,
} from "lucide-react";
import {
  getHealth,
  getReviewDue,
  getReviewStats,
  getScheduleStatus,
  submitReview,
  suspendReview,
  type HealthResponse,
  type ReviewQueueItem,
  type ReviewStatsResponse,
  type ReviewRating,
  type ScheduleStatusResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ReviewPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [reviewItems, setReviewItems] = useState<ReviewQueueItem[]>([]);
  const [reviewStats, setReviewStats] = useState<ReviewStatsResponse | null>(null);
  const [scheduleStatus, setScheduleStatus] = useState<ScheduleStatusResponse | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(0);

  const currentItem = reviewItems[currentIndex] || null;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, dueData, statsData, scheduleData] = await Promise.all([
        getHealth(),
        getReviewDue(50),
        getReviewStats(),
        getScheduleStatus().catch(() => null), // Schedule status is optional
      ]);
      setHealth(healthData);
      setReviewItems(dueData.items);
      setReviewStats(statsData);
      setScheduleStatus(scheduleData);
      setCurrentIndex(0);
      setShowAnswer(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      if (!currentItem) return;

      if (!showAnswer) {
        if (e.code === "Space" || e.code === "Enter") {
          e.preventDefault();
          setShowAnswer(true);
        }
      } else {
        switch (e.code) {
          case "Digit1":
          case "Numpad1":
            e.preventDefault();
            handleRating("again");
            break;
          case "Digit2":
          case "Numpad2":
            e.preventDefault();
            handleRating("hard");
            break;
          case "Digit3":
          case "Numpad3":
            e.preventDefault();
            handleRating("good");
            break;
          case "Digit4":
          case "Numpad4":
            e.preventDefault();
            handleRating("easy");
            break;
          case "KeyS":
            e.preventDefault();
            handleSuspend();
            break;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // Note: handleRating and handleSuspend are intentionally not in deps
    // to avoid recreating listener on every render. They use current state via closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentItem, showAnswer]);

  const handleRating = async (rating: ReviewRating) => {
    if (!currentItem || submitting) return;

    setSubmitting(true);
    try {
      await submitReview(currentItem.content_id, rating);
      setSessionComplete((prev) => prev + 1);

      // Move to next item
      if (currentIndex < reviewItems.length - 1) {
        setCurrentIndex((prev) => prev + 1);
        setShowAnswer(false);
      } else {
        // All done for now
        setReviewItems([]);
      }

      // Refresh stats
      const statsData = await getReviewStats();
      setReviewStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSuspend = async () => {
    if (!currentItem) return;

    try {
      await suspendReview(currentItem.content_id);
      // Remove from list and move to next
      const newItems = reviewItems.filter((_, i) => i !== currentIndex);
      setReviewItems(newItems);
      if (currentIndex >= newItems.length && newItems.length > 0) {
        setCurrentIndex(newItems.length - 1);
      }
      setShowAnswer(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to suspend item");
    }
  };

  const getStateColor = (state: string) => {
    switch (state) {
      case "Learning":
        return "bg-blue-500/10 text-blue-500 border-blue-500/20";
      case "Review":
        return "bg-green-500/10 text-green-500 border-green-500/20";
      case "Relearning":
        return "bg-orange-500/10 text-orange-500 border-orange-500/20";
      default:
        return "bg-gray-500/10 text-gray-500 border-gray-500/20";
    }
  };

  const progressPercentage = reviewItems.length > 0
    ? ((currentIndex) / reviewItems.length) * 100
    : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Daily Review</h1>
          <p className="text-muted-foreground">
            Practice with spaced repetition
          </p>
        </div>
        <div className="flex items-center gap-3">
          {sessionComplete > 0 && (
            <Badge variant="secondary" className="gap-1">
              <CheckCircle2 className="h-3 w-3" />
              {sessionComplete} completed
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
            <RotateCcw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3">
            <Card>
              <CardContent className="p-12">
                <div className="h-64 bg-muted rounded animate-pulse" />
              </CardContent>
            </Card>
          </div>
          <div className="space-y-4">
            <Card>
              <CardContent className="p-6">
                <div className="h-32 bg-muted rounded animate-pulse" />
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Main Review Area */}
          <div className="lg:col-span-3 space-y-4">
            {/* Progress Bar */}
            {reviewItems.length > 0 && (
              <div className="flex items-center gap-4">
                <Progress value={progressPercentage} className="flex-1 h-2" />
                <span className="text-sm text-muted-foreground whitespace-nowrap">
                  {currentIndex + 1} / {reviewItems.length}
                </span>
              </div>
            )}

            {/* Flashcard */}
            {currentItem ? (
              <Card className="overflow-hidden">
                <CardHeader className="bg-muted/30">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge variant="outline" className={getStateColor(currentItem.state)}>
                        {currentItem.is_new ? "New" : currentItem.state}
                      </Badge>
                      <Badge variant="outline">{currentItem.content_type}</Badge>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <TrendingUp className="h-4 w-4" />
                      <span>S: {currentItem.stability?.toFixed(1) || "0.0"}</span>
                      <Separator orientation="vertical" className="h-4" />
                      <Zap className="h-4 w-4" />
                      <span>D: {currentItem.difficulty?.toFixed(1) || "0.0"}</span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="p-8">
                  {/* Title */}
                  <h2 className="text-xl font-semibold mb-6 text-center">
                    {currentItem.title}
                  </h2>

                  {/* Content Area */}
                  <div className="min-h-[200px] flex items-center justify-center">
                    {showAnswer ? (
                      <div className="w-full">
                        <div className="p-6 rounded-lg bg-muted/50 mb-8">
                          <p className="whitespace-pre-wrap leading-relaxed">
                            {currentItem.preview_text}
                          </p>
                        </div>

                        {/* Rating Buttons */}
                        <div className="grid grid-cols-4 gap-3">
                          <Button
                            variant="outline"
                            className="h-20 flex-col gap-2 border-2 hover:border-red-500 hover:bg-red-500/10 group"
                            onClick={() => handleRating("again")}
                            disabled={submitting}
                          >
                            <span className="text-lg font-semibold group-hover:text-red-500">
                              Again
                            </span>
                            <span className="text-xs text-muted-foreground">&lt;1m</span>
                            <kbd className="text-xs bg-muted px-1.5 py-0.5 rounded">1</kbd>
                          </Button>
                          <Button
                            variant="outline"
                            className="h-20 flex-col gap-2 border-2 hover:border-orange-500 hover:bg-orange-500/10 group"
                            onClick={() => handleRating("hard")}
                            disabled={submitting}
                          >
                            <span className="text-lg font-semibold group-hover:text-orange-500">
                              Hard
                            </span>
                            <span className="text-xs text-muted-foreground">~10m</span>
                            <kbd className="text-xs bg-muted px-1.5 py-0.5 rounded">2</kbd>
                          </Button>
                          <Button
                            variant="outline"
                            className="h-20 flex-col gap-2 border-2 hover:border-green-500 hover:bg-green-500/10 group"
                            onClick={() => handleRating("good")}
                            disabled={submitting}
                          >
                            <span className="text-lg font-semibold group-hover:text-green-500">
                              Good
                            </span>
                            <span className="text-xs text-muted-foreground">~1d</span>
                            <kbd className="text-xs bg-muted px-1.5 py-0.5 rounded">3</kbd>
                          </Button>
                          <Button
                            variant="outline"
                            className="h-20 flex-col gap-2 border-2 hover:border-blue-500 hover:bg-blue-500/10 group"
                            onClick={() => handleRating("easy")}
                            disabled={submitting}
                          >
                            <span className="text-lg font-semibold group-hover:text-blue-500">
                              Easy
                            </span>
                            <span className="text-xs text-muted-foreground">~4d</span>
                            <kbd className="text-xs bg-muted px-1.5 py-0.5 rounded">4</kbd>
                          </Button>
                        </div>

                        {/* Suspend Button */}
                        <div className="flex justify-center mt-4">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleSuspend}
                            className="text-muted-foreground gap-2"
                          >
                            <Pause className="h-4 w-4" />
                            Suspend this item
                            <kbd className="text-xs bg-muted px-1.5 py-0.5 rounded ml-1">S</kbd>
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center">
                        <p className="text-muted-foreground mb-6">
                          Try to recall the content before revealing
                        </p>
                        <Button
                          size="lg"
                          onClick={() => setShowAnswer(true)}
                          className="gap-2"
                        >
                          <Eye className="h-5 w-5" />
                          Show Answer
                          <kbd className="ml-2 text-xs bg-primary-foreground/20 px-1.5 py-0.5 rounded">
                            Space
                          </kbd>
                        </Button>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="py-16">
                  <div className="text-center">
                    <CheckCircle2 className="h-16 w-16 mx-auto mb-4 text-green-500" />
                    <h2 className="text-2xl font-bold mb-2">All caught up!</h2>
                    <p className="text-muted-foreground mb-6">
                      {sessionComplete > 0
                        ? `Great work! You completed ${sessionComplete} reviews.`
                        : "No items are due for review right now."}
                    </p>
                    <div className="flex gap-3 justify-center">
                      <Button variant="outline" onClick={loadData}>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Check Again
                      </Button>
                      <Link href="/">
                        <Button>Back to Dashboard</Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Queue Stats */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Queue Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-lg bg-blue-500/10 text-center">
                    <p className="text-xl font-bold text-blue-500">
                      {reviewStats?.new || 0}
                    </p>
                    <p className="text-xs text-muted-foreground">New</p>
                  </div>
                  <div className="p-3 rounded-lg bg-yellow-500/10 text-center">
                    <p className="text-xl font-bold text-yellow-500">
                      {reviewStats?.learning || 0}
                    </p>
                    <p className="text-xs text-muted-foreground">Learning</p>
                  </div>
                  <div className="p-3 rounded-lg bg-green-500/10 text-center">
                    <p className="text-xl font-bold text-green-500">
                      {reviewStats?.review || 0}
                    </p>
                    <p className="text-xs text-muted-foreground">Review</p>
                  </div>
                  <div className="p-3 rounded-lg bg-orange-500/10 text-center">
                    <p className="text-xl font-bold text-orange-500">
                      {reviewStats?.due_now || 0}
                    </p>
                    <p className="text-xs text-muted-foreground">Due Now</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Keyboard Shortcuts */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Keyboard className="h-4 w-4" />
                  Shortcuts
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Show answer</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">Space</kbd>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Again</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">1</kbd>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Hard</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">2</kbd>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Good</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">3</kbd>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Easy</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">4</kbd>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Suspend</span>
                    <kbd className="bg-muted px-2 py-0.5 rounded text-xs">S</kbd>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Schedule Info */}
            {scheduleStatus && (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    Daily Schedule
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Time</span>
                      <span>{scheduleStatus.scheduled_time}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Timezone</span>
                      <span className="text-xs">{scheduleStatus.timezone}</span>
                    </div>
                    {scheduleStatus.next_run && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Next</span>
                        <span className="text-xs">
                          {new Date(scheduleStatus.next_run).toLocaleString()}
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Status</span>
                      <Badge
                        variant={scheduleStatus.enabled ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {scheduleStatus.status}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* System Status */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">System</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {health?.services?.map((service) => (
                    <div
                      key={service.name}
                      className="flex items-center justify-between text-sm"
                    >
                      <div className="flex items-center gap-2">
                        <div
                          className={cn(
                            "h-2 w-2 rounded-full",
                            service.status === "healthy" ? "bg-green-500" : "bg-red-500"
                          )}
                        />
                        <span>{service.name}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {service.status === "healthy" ? "OK" : "Error"}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
