"use client";

import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";

export function Header() {
  return (
    <header className="border-b border-border">
      <div className="container mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold text-lg">
            Knowledge
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Search
            </Link>
            <Link
              href="/content"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Content
            </Link>
            <Link
              href="/review"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Review
            </Link>
          </nav>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
