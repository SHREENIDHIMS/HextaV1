"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Shield,
  UserCheck,
  UserX,
  X,
} from "lucide-react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { getSession, clearSession } from "@/lib/auth";
import { listUsers, patchUser, UserItem, ApiError } from "@/lib/api-client";

// ── Role badge ───────────────────────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
  const classes =
    role === "admin"
      ? "bg-primary/10 text-primary border-primary/20"
      : "bg-muted text-muted-foreground border-border/60";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${classes}`}
    >
      {role === "admin" && <Shield className="size-2.5" />}
      {role}
    </span>
  );
}

// ── Status badge ─────────────────────────────────────────────────────────────
function ActiveBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        active
          ? "bg-green-500/10 text-green-500"
          : "bg-muted text-muted-foreground"
      }`}
    >
      <span
        className={`size-1.5 rounded-full ${active ? "bg-green-500" : "bg-muted-foreground"}`}
      />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

// ── Shimmer ───────────────────────────────────────────────────────────────────
function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`shimmer rounded-lg ${className}`} />;
}

// ── Confirm Dialog ────────────────────────────────────────────────────────────
function ConfirmDialog({
  user,
  action,
  onConfirm,
  onCancel,
}: {
  user: UserItem;
  action: "activate" | "deactivate";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="absolute inset-0 bg-background/70 backdrop-blur-sm"
        onClick={onCancel}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative z-10 w-full max-w-sm rounded-2xl border border-border/60 bg-card p-6 shadow-2xl"
      >
        <button
          onClick={onCancel}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="size-4" />
        </button>
        <div className="flex items-start gap-3 mb-4">
          <div
            className={`flex size-10 shrink-0 items-center justify-center rounded-xl ${
              action === "deactivate"
                ? "bg-destructive/10"
                : "bg-green-500/10"
            }`}
          >
            {action === "deactivate" ? (
              <UserX
                className={`size-5 ${
                  action === "deactivate"
                    ? "text-destructive"
                    : "text-green-500"
                }`}
              />
            ) : (
              <UserCheck className="size-5 text-green-500" />
            )}
          </div>
          <div>
            <h3 className="font-semibold text-foreground">
              {action === "deactivate" ? "Deactivate User" : "Activate User"}
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {action === "deactivate"
                ? `${user.email} will no longer be able to sign in.`
                : `${user.email} will regain access to the platform.`}
            </p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="rounded-xl border border-border/60 bg-muted/30 px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`rounded-xl px-4 py-2 text-sm font-semibold text-white transition-all active:scale-95 ${
              action === "deactivate"
                ? "bg-destructive hover:opacity-90"
                : "gradient-brand hover:opacity-90"
            }`}
          >
            {action === "deactivate" ? "Deactivate" : "Activate"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AdminPage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{
    user: UserItem;
    action: "activate" | "deactivate";
  } | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getSession().then((s) => {
      if (cancelled) return;
      if (s) {
        setToken("active");
      } else {
        clearSession();
      }
      setAuthChecked(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    listUsers()
      .then((r) => setUsers(r.users))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setError("Admin access required.");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load users");
        }
      })
      .finally(() => setLoading(false));
  }, [token]);

  const handleToggle = async (user: UserItem) => {
    if (!token) return;
    const action = user.is_active ? "deactivate" : "activate";
    setPending({ user, action });
  };

  const confirmToggle = async () => {
    if (!pending || !token) return;
    const { user } = pending;
    setPending(null);
    setToggling(user.id);
    try {
      const updated = await patchUser(
        user.id,
        { is_active: !user.is_active }
      );
      setUsers((prev) =>
        prev.map((u) =>
          u.id === updated.id ? { ...u, is_active: updated.is_active } : u
        )
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update user"
      );
    } finally {
      setToggling(null);
    }
  };

  if (!authChecked) return null;
  if (!token) return <LoginForm onSuccess={() => void getSession().then((s) => setToken(s ? "active" : null))} />;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-y-auto scrollbar">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="flex items-center gap-3 mb-1">
              <div className="flex size-9 items-center justify-center rounded-xl gradient-brand">
                <Shield className="size-5 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">Admin</h1>
            </div>
            <p className="text-sm text-muted-foreground ml-12">
              Manage users and platform access. All changes are enforced
              server-side via RBAC.
            </p>
          </motion.div>

          {/* Error */}
          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
              <AlertTriangle className="size-4 text-destructive shrink-0 mt-0.5" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Users Table */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.35 }}
            className="rounded-2xl border border-border/60 bg-card overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-border/50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">Users</h2>
              <span className="text-xs text-muted-foreground">
                {users.length} total
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40 text-left bg-muted/20">
                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
                      User
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Role
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Department
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Status
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Joined
                    </th>
                    <th className="px-6 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground/60 text-right">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    [...Array(4)].map((_, i) => (
                      <tr key={i} className="border-b border-border/30">
                        <td className="px-6 py-4" colSpan={6}>
                          <Skeleton className="h-5" />
                        </td>
                      </tr>
                    ))
                  ) : users.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="py-10 text-center text-sm text-muted-foreground"
                      >
                        No users found.
                      </td>
                    </tr>
                  ) : (
                    users.map((u, i) => (
                      <motion.tr
                        key={u.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.04 }}
                        className="border-b border-border/30 last:border-0 hover:bg-muted/20 transition-colors"
                      >
                        <td className="px-6 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="flex size-7 shrink-0 items-center justify-center rounded-full gradient-brand text-white text-[10px] font-bold">
                              {(u.email || "?").slice(0, 2).toUpperCase()}
                            </div>
                            <div>
                              <p className="font-medium text-foreground text-xs">
                                {u.full_name || u.email}
                              </p>
                              {u.full_name && (
                                <p className="text-[10px] text-muted-foreground">
                                  {u.email}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3.5">
                          <RoleBadge role={u.role} />
                        </td>
                        <td className="px-4 py-3.5 text-xs text-muted-foreground">
                          {u.department || "—"}
                        </td>
                        <td className="px-4 py-3.5">
                          <ActiveBadge active={u.is_active} />
                        </td>
                        <td className="px-4 py-3.5 text-xs text-muted-foreground">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-3.5 text-right">
                          <button
                            type="button"
                            disabled={toggling === u.id}
                            onClick={() => handleToggle(u)}
                            className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition-all duration-150 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
                              u.is_active
                                ? "border border-destructive/30 text-destructive hover:bg-destructive/10"
                                : "border border-green-500/30 text-green-500 hover:bg-green-500/10"
                            }`}
                          >
                            {toggling === u.id
                              ? "Saving…"
                              : u.is_active
                              ? "Deactivate"
                              : "Activate"}
                          </button>
                        </td>
                      </motion.tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </motion.div>
        </div>
      </main>

      {/* Confirm dialog */}
      <AnimatePresence>
        {pending && (
          <ConfirmDialog
            user={pending.user}
            action={pending.action}
            onConfirm={confirmToggle}
            onCancel={() => setPending(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
