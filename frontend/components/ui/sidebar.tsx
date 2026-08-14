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
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { getCachedSession, getToken, signOut } from "@/lib/auth";
import { Orb } from "@/components/ui/orb";
import { Badge } from "@/components/ui/badge";

const navMain = [
  { label: "Chat", href: "/", icon: MessageSquare },
  { label: "Doc Upload", href: "/uploads", icon: Upload, adminOnly: true },
  { label: "Analytics", href: "/analytics", icon: BarChart3, adminOnly: true },
  { label: "Settings", href: "/settings", icon: Settings },
];

const navAdmin = [{ label: "Admin", href: "/admin", icon: Shield }];

type NavItem = (typeof navMain)[number];

const ADMIN_ROLES = new Set(["admin", "super_admin"]);

function isAdminRole(role: string): boolean {
  return ADMIN_ROLES.has(role);
}

// Session identity now comes from the httpOnly-cookie session (fetched
// via /auth/verify and cached in memory), not from decoding a JWT — the
// token is unreadable to JS by design.

function getUserInitials(session: { email?: string; userId?: number } | null): string {
  const email = session?.email;
  if (email) return email.slice(0, 2).toUpperCase();
  return "HX";
}

function getUserEmail(session: { email?: string } | null): string {
  return session?.email || "user@hexa.local";
}

function getUserRole(session: { role?: string } | null): string {
  return session?.role || "user";
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
            {active && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-primary" />
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
}: {
  collapsed: boolean;
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

/* ── User profile block with role badge ── */
function UserProfile({
  session,
  collapsed,
}: {
  session: { email?: string; userId?: number; role?: string } | null;
  collapsed: boolean;
}) {
  const initials = getUserInitials(session);
  const email = getUserEmail(session);
  const role = getUserRole(session);

  const roleColor = role === "admin" ? "text-warning" : "text-primary";
  const roleBg =
    role === "admin"
      ? "bg-warning/10 border-warning/20"
      : "bg-primary/10 border-primary/20";

  if (collapsed) {
    return (
      <div className="flex justify-center px-3 pb-3">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
          {initials}
        </div>
      </div>
    );
  }

  return (
    <div className="px-3 pb-3">
      <div className="flex items-center gap-2.5 rounded-xl border border-border/60 bg-muted/30 p-3">
        <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
          {initials}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-foreground truncate">
            {email}
          </p>
          <div className="flex items-center gap-1 mt-0.5">
            <Badge
              variant="outline"
              className={cn(
                "text-[9px] font-medium px-1.5 py-0",
                roleBg,
                roleColor
              )}
            >
              {role}
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Sidebar({
  onSignOut,
  onNewChat,
  mobileOpen = false,
  onMobileClose,
}: {
  onSignOut?: () => void;
  onNewChat?: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}) {
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);

  const handleSignOut = () => {
    void signOut();
    onSignOut?.();
    router.replace("/");
  };

  const handleNewChat = () => {
    onNewChat?.();
    router.push("/");
  };

  if (typeof window === "undefined") return null;
  const token = getToken();
  if (!token) return null;

  const session = getCachedSession();
  const role = getUserRole(session);
  const isAdmin = isAdminRole(role);
  const visibleMain = navMain.filter(
    (item) => !item.adminOnly || isAdmin
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
          {<BrandHeader collapsed={isCollapsed} />}
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
              items={visibleMain}
              collapsed={isCollapsed}
              onNavigate={onNav}
            />
          </section>
        </nav>

        {/* Admin Section */}
        {isAdmin && (
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
        )}

        <Separator className="opacity-50" />

        {/* User Profile */}
        <UserProfile session={session} collapsed={isCollapsed} />

        {/* Sign Out */}
        <div className={cn("px-2 pb-3", isCollapsed && "flex flex-col items-center gap-2")}>
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
        className="fixed left-3 top-16 z-50 md:hidden border-border bg-background/80 backdrop-blur-sm"
        onClick={() => onMobileClose?.()}
        aria-label="Open navigation"
        title="Open navigation"
      >
        <Menu className="size-5" />
      </Button>

      {/* Mobile / tablet: drawer overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="sidebar-mobile-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 md:hidden bg-background/70 backdrop-blur-sm"
              onClick={() => onMobileClose?.()}
              aria-hidden
            />
            <motion.aside
              key="sidebar-mobile"
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
              className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border/60 bg-sidebar shadow-xl md:hidden"
            >
              {sidebarContent(false, () => onMobileClose?.())}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
