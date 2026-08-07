"use client";

import { useEffect, useState } from "react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import { verifyToken } from "@/lib/api-client";
import { ThemeToggle } from "@/components/theme/toggle";

export default function SettingsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<{
    valid: boolean;
    user_id?: number;
    email?: string;
 } | null>(null);

  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) setToken(t);
    else clearToken();
  }, []);

  useEffect(() => {
    if (!token) return;
    verifyToken(token)
      .then(setMe)
      .catch(() => setMe({ valid: false }));
  }, [token]);

  if (!token) return <LoginForm onSuccess={() => setToken(getToken())} />;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <h1 className="text-2xl font-bold mb-4">Settings</h1>

          <section className="mb-6">
            <h2 className="text-base font-semibold mb-1">Appearance</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Choose between light, dark, or system theme.
            </p>
            <ThemeToggle />
          </section>

          {me && (
            <p className="text-sm text-muted-foreground mb-2">
              Authenticated as user #{me.user_id} ({me.email ?? "—"}) — valid:{" "}
              {String(me.valid)}
            </p>
          )}
          <p className="text-sm text-muted-foreground">
            Hexta is extractive-only: answers come verbatim from Postgres full
            text search, never generated text. There is no LLM/embedding service
            to configure here — JWT + RBAC settings live in backend/.env.
          </p>
        </div>
      </main>
    </div>
  );
}
