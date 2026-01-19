"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  Search,
  Library,
  Brain,
  FileText,
  Play,
  Moon,
  Sun,
  Laptop,
  PenLine,
  Download,
  Settings,
  BarChart3,
  Webhook,
  Puzzle,
} from "lucide-react";
import { useTheme } from "next-themes";

export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { setTheme } = useTheme();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  return (
    <>
      {/* Keyboard hint in corner */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 hidden md:flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground bg-card border border-border rounded-lg shadow-sm hover:bg-accent transition-colors"
      >
        <span>Quick actions</span>
        <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Type a command or search..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>

          <CommandGroup heading="Navigation">
            <CommandItem onSelect={() => runCommand(() => router.push("/"))}>
              <LayoutDashboard className="mr-2 h-4 w-4" />
              <span>Dashboard</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/search"))}>
              <Search className="mr-2 h-4 w-4" />
              <span>Search</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/content"))}>
              <Library className="mr-2 h-4 w-4" />
              <span>Content Library</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/review"))}>
              <Brain className="mr-2 h-4 w-4" />
              <span>Review</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/analytics"))}>
              <BarChart3 className="mr-2 h-4 w-4" />
              <span>Analytics</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/webhooks"))}>
              <Webhook className="mr-2 h-4 w-4" />
              <span>Webhooks</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/plugins"))}>
              <Puzzle className="mr-2 h-4 w-4" />
              <span>Plugins</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/settings"))}>
              <Settings className="mr-2 h-4 w-4" />
              <span>Settings</span>
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Quick Actions">
            <CommandItem
              onSelect={() => runCommand(() => router.push("/capture"))}
            >
              <PenLine className="mr-2 h-4 w-4" />
              <span>Quick Capture</span>
            </CommandItem>
            <CommandItem
              onSelect={() => runCommand(() => router.push("/review"))}
            >
              <Play className="mr-2 h-4 w-4" />
              <span>Start Review Session</span>
            </CommandItem>
            <CommandItem
              onSelect={() => runCommand(() => {
                router.push("/search");
                // Focus search input after navigation
                setTimeout(() => {
                  const input = document.querySelector('input[type="text"]');
                  if (input) (input as HTMLInputElement).focus();
                }, 100);
              })}
            >
              <FileText className="mr-2 h-4 w-4" />
              <span>Search Knowledge Base</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => router.push("/export"))}>
              <Download className="mr-2 h-4 w-4" />
              <span>Export/Import</span>
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />

          <CommandGroup heading="Theme">
            <CommandItem onSelect={() => runCommand(() => setTheme("light"))}>
              <Sun className="mr-2 h-4 w-4" />
              <span>Light Mode</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme("dark"))}>
              <Moon className="mr-2 h-4 w-4" />
              <span>Dark Mode</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme("system"))}>
              <Laptop className="mr-2 h-4 w-4" />
              <span>System Theme</span>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
