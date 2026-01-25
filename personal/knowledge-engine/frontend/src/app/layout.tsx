import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Knowledge Engine",
  description: "Enterprise-grade knowledge infrastructure for AI applications",
  keywords: ["knowledge", "search", "AI", "RAG", "semantic search"],
  authors: [{ name: "Knowledge Engine Team" }],
  openGraph: {
    title: "Knowledge Engine",
    description: "Enterprise-grade knowledge infrastructure for AI applications",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen bg-background">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
