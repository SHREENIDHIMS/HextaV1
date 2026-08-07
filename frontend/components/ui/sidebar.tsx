"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart3,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  Shield,
  SquarePen,
  Upload,
  X,
} from "lucide-react";
import { motion } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import { Orb } from "@/components/ui/orb";

const navMain = [
  { label: "Chat", href: "/", icon: MessageSquare },
  { label: "Doc Upload", href: "/uploads", icon: Upload },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

const navAdmin = [{ label: "Admin", href: "/admin", icon: Shield }];

type NavItem = (typeof navMain)[number];

function getUserInitials(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    const email: string = payload.email || payload.sub || "?";
    return email.slice(0, 2).toUpperCase();
  } catch {
    return "HX";
  }
}

function getUserEmail(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.email || "user@hexa.local";
  } catch {
    return "user@hexa.local";
  }
}

function SectionLabel({
  collapsed,
  children,
}: {
  collapsed: boolean;
  children: React.ReactNode;
}) {
  if (collapsed) return null;
  return (
    <p className="px-3 pb-1.5 pt-3 text-[0.65rem] font-semibold uppercase tracking-widest text-muted-foreground/50">
      {children}
    </p>
  );
}

function NavLinks({
  items,
  collapsed,
  onNavigate,
}: {
  items: NavItem[];
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  return (
    <div className="space-y-0.5">
      {items.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            title={item.label}
            aria-label={item.label}
            className={cn(
              "group relative flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed ? "justify-center py-2.5 px-2" : "px-3 py-2.5",
              active
                ? "bg-primary/15 text-primary shadow-sm shadow-primary/10"
                : "text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            )}
          >
            {/* Active indicator bar */}
            {active && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full gradient-brand" />
            )}
            <item.icon
              className={cn(
                "size-4 shrink-0 transition-transform duration-200",
                active ? "text-primary" : "group-hover:scale-110"
              )}
            />
            {!collapsed && <span>{item.label}</span>}
          </Link>
        );
      })}
    </div>
  );
}

function BrandHeader({
  collapsed,
  token,
}: {
  collapsed: boolean;
  token: string;
}) {
  if (collapsed) {
    return (
      <div className="flex h-16 items-center justify-center">
        <Orb className="size-8" />
      </div>
    );
  }
  return (
    <div className="px-4 py-4 flex items-center gap-3">
      <Orb className="size-8 shrink-0" />
      <div className="min-w-0">
        <h2 className="text-lg font-bold gradient-brand-text leading-tight">
          Hexta
        </h2>
        <p className="text-[10px] text-muted-foreground/60 font-medium tracking-wide truncate">
          Mortgage Knowledge Assistant
        </p>
      </div>
    </div>
  );
}

export default function Sidebar({
  onSignOut,
  onNewChat,
}: {
  onSignOut?: () => void;
  onNewChat?: () => void;
}) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleSignOut = () => {
    clearToken();
    onSignOut?.();
    router.replace("/");
  };

  const handleNewChat = () => {
    onNewChat?.();
    router.push("/");
  };

  if (typeof window === "undefined") return null;
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;

  const initials = getUserInitials(token);
  const email = getUserEmail(token);

  const collapseButton = (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={() => setCollapsed((c) => !c)}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      className="text-muted-foreground hover:text-foreground size-8"
    >
      {collapsed ? (
        <PanelLeftOpen className="size-4" />
      ) : (
        <PanelLeftClose className="size-4" />
      )}
    </Button>
  );

  const sidebarContent = (
    isCollapsed: boolean,
    onNav: (() => void) | undefined
  ) => {
    return (
      <div className="flex h-full flex-col">
        {/* Header */}
        <div
          className={cn(
            "flex items-center border-b border-border/60",
            isCollapsed ? "h-16 justify-center" : "justify-between pr-2 pl-0"
          )}
        >
          {<BrandHeader collapsed={isCollapsed} token={token} />}
          {!isCollapsed && collapseButton}
          {isCollapsed && collapseButton}
        </div>

        {/* New Chat Button */}
        <div className={cn("p-2", isCollapsed && "pb-1 flex justify-center")}>
          <button
            type="button"
            onClick={handleNewChat}
            title="New chat"
            aria-label="New chat"
            className={cn(
              "group flex items-center gap-2 rounded-xl text-sm font-medium transition-all duration-200",
              "border border-border/70 bg-muted/40 hover:bg-primary/10 hover:border-primary/40 hover:text-primary",
              "focus-visible:ring-2 focus-visible:ring-ring outline-none",
              isCollapsed
                ? "justify-center p-2.5"
                : "w-full px-3 py-2.5 justify-start"
            )}
          >
            <SquarePen className="size-4 shrink-0 transition-transform duration-200 group-hover:scale-110" />
            {!isCollapsed && "New chat"}
          </button>
        </div>

        {/* Navigation */}
        <nav
          className="flex-1 space-y-0 overflow-y-auto px-2 pb-2"
          aria-label="Main"
        >
          <section aria-label="Workspace">
            <SectionLabel collapsed={isCollapsed}>Workspace</SectionLabel>
            <NavLinks
              items={navMain}
              collapsed={isCollapsed}
              onNavigate={onNav}
            />
          </section>
        </nav>

        {/* Admin Section */}
        <div className="px-2 pb-2">
          <div className="rounded-xl border border-border/50 bg-muted/20 py-1 px-1">
            <SectionLabel collapsed={isCollapsed}>Admin</SectionLabel>
            <NavLinks
              items={navAdmin}
              collapsed={isCollapsed}
              onNavigate={onNav}
            />
          </div>
        </div>

        <Separator className="opacity-50" />

        {/* User Avatar + Sign Out */}
        <div className={cn("px-2 py-3", isCollapsed && "flex flex-col items-center gap-2")}>
          {!isCollapsed && (
            <div className="flex items-center gap-2 px-1 pb-2">
              <div className="flex size-7 shrink-0 items-center justify-center rounded-full gradient-brand text-white text-xs font-bold">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-foreground truncate">
                  {email}
                </p>
                <p className="text-[10px] text-muted-foreground/60">
                  Active session
                </p>
              </div>
            </div>
          )}
          {isCollapsed && (
            <div className="flex size-7 shrink-0 items-center justify-center rounded-full gradient-brand text-white text-xs font-bold mb-1">
              {initials}
            </div>
          )}
          <button
            type="button"
            onClick={handleSignOut}
            title={isCollapsed ? "Sign out" : undefined}
            aria-label={isCollapsed ? "Sign out" : undefined}
            className={cn(
              "group flex items-center gap-2 rounded-xl text-xs font-medium transition-all duration-200",
              "text-muted-foreground hover:text-red-400 hover:bg-red-500/10",
              "focus-visible:ring-2 focus-visible:ring-ring outline-none",
              isCollapsed ? "justify-center p-2" : "w-full px-3 py-2 justify-start"
            )}
          >
            <LogOut className="size-3.5 shrink-0 transition-transform duration-200 group-hover:-translate-x-0.5" />
            {!isCollapsed && "Sign out"}
          </button>
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Desktop / tablet: collapsible rail */}
      <aside
        className={cn(
          "hidden md:flex shrink-0 flex-col overflow-hidden border-r border-border/60 bg-sidebar transition-[width] duration-300 ease-in-out",
          collapsed ? "w-14" : "w-64"
        )}
      >
        {sidebarContent(collapsed, undefined)}
      </aside>

      {/* Mobile: hamburger trigger */}
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="fixed left-3 top-3 z-50 md:hidden border-border bg-background/80 backdrop-blur-sm"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
        title="Open navigation"
      >
        <Menu className="size-5" />
      </Button>

      {/* Mobile / tablet: drawer overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <motion.div
            initial={{ x: -300 }}
            animate={{ x: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border/60 bg-sidebar shadow-2xl"
          >
            <div className="flex justify-end p-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation"
              >
                <X className="size-5" />
              </Button>
            </div>
            <div className="h-[calc(100%-3rem)]">
              {sidebarContent(false, () => setMobileOpen(false))}
            </div>
          </motion.div>
        </div>
      )}
    </>
  );
}