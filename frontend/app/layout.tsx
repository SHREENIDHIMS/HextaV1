import "@/styles/globals.css";
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
