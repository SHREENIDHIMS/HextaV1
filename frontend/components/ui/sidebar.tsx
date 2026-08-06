"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Home, LogOut, Settings, Shield, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";

const nav = [
  { label: "Chat", href: "/", icon: Home },
  { label: "Uploads", href: "/uploads", icon: Upload },
  { label: "Settings", href: "/settings", icon: Settings },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Admin", href: "/admin", icon: Shield },
];

export default function Sidebar({ onSignOut }: { onSignOut?: () => void }) {
  const router = useRouter();
  const pathname = usePathname();

  const handleSignOut = () => {
    clearToken();
    onSignOut?.();
    router.replace("/");
  };

  if (typeof window === "undefined") return null;
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;

  return (
    <aside className="flex flex-col w-64 border-r bg-background">
      <div className="p-4 border-b">
        <h2 className="text-xl font-bold">Hexta</h2>
        <p className="text-xs text-muted-foreground">
          Mortgage Knowledge Assistant
        </p>
      </div>
      <nav className="flex-1 p-2 space-y-1" aria-label="Main">
        {nav.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground",
              pathname === n.href
                ? "bg-accent text-accent-foreground"
                : "transparent"
            )}
          >
            <n.icon className="w-4 h-4" />
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="p-3 border-t">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start gap-3"
          onClick={handleSignOut}
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </Button>
      </div>
    </aside>
  );
}
