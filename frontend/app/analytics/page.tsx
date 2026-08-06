"use client";

import { useEffect, useState } from "react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";

export default function AnalyticsPage() {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) setToken(t);
    else clearToken();
  }, []);

  if (!token) return <LoginForm onSuccess={() => setToken(getToken())} />;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <h1 className="text-2xl font-bold mb-4">Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Search volume, confidence distributions, and top FAQs are recorded
            by the audit logger and benchmark reports (see evaluation/). A live
            dashboard is future work.
          </p>
        </div>
      </main>
    </div>
  );
}
