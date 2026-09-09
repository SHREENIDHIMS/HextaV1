import "@/styles/globals.css";
// Self-hosted Inter (bundled via @fontsource/inter) — no external font
// request, CSP-friendly (font-src 'self' data:). Latin subset only keeps
// the bundle small; weights 400-700 cover the app's design tokens.
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import { cn } from "@/lib/utils";
import { ThemeProvider, themeInitScript } from "@/components/theme/provider";

export const metadata = {
  title: "Hexta — Mortgage Knowledge Assistant",
  description: "Ask questions about mortgage lending requirements, documents, and policies.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={cn("font-sans")} suppressHydrationWarning>
      <body className="font-sans antialiased" suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
