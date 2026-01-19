"use client";

import { Toaster as SonnerToaster } from "sonner";
import { useTheme } from "next-themes";

export function Toaster() {
  const { theme } = useTheme();

  return (
    <SonnerToaster
      theme={theme as "light" | "dark" | "system"}
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        duration: 4000,
        classNames: {
          toast: "border-border",
          title: "text-foreground",
          description: "text-muted-foreground",
        },
      }}
    />
  );
}
