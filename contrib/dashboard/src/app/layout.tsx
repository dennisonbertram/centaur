import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider, UserButton, Show, SignInButton } from "@clerk/nextjs";
import Link from "next/link";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Centaur",
  description: "Managed AI agent deployments",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className={`${geistSans.className} min-h-full flex flex-col bg-white text-gray-900`}>
        <ThemeProvider>
          <ClerkProvider>
            <nav className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
              <div className="mx-auto max-w-5xl px-6">
                <div className="flex h-14 items-center justify-between">
                  <div className="flex items-center gap-8">
                    <Link
                      href="/"
                      className="flex items-center gap-2 text-base font-semibold tracking-tight"
                    >
                      <svg
                        className="h-5 w-5"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2" />
                        <line x1="12" y1="22" x2="12" y2="15.5" />
                        <polyline points="22 8.5 12 15.5 2 8.5" />
                      </svg>
                      Centaur
                    </Link>
                    <Show when="signed-in">
                      <div className="flex gap-6 text-sm text-muted-foreground">
                        <Link
                          href="/deployments"
                          className="transition-colors hover:text-foreground"
                        >
                          Deployments
                        </Link>
                        <Link
                          href="/usage"
                          className="transition-colors hover:text-foreground"
                        >
                          Usage
                        </Link>
                      </div>
                    </Show>
                  </div>
                  <div className="flex items-center gap-3">
                    <ThemeToggle />
                    <Show when="signed-out">
                      <SignInButton>
                        <button className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
                          Sign in
                        </button>
                      </SignInButton>
                    </Show>
                    <Show when="signed-in">
                      <UserButton />
                    </Show>
                  </div>
                </div>
              </div>
            </nav>
            <main className="flex-1">
              <div className="mx-auto max-w-5xl px-6 py-8">{children}</div>
            </main>
          </ClerkProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
