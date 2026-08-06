"use client";

import { useEffect, useState } from "react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";

export default function AdminPage() {
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
          <h1 className="text-2xl font-bold mb-4">Admin</h1>
          <p className="text-sm text-muted-foreground">
            Admin-only endpoints (documents management and analytics) are
            enforced server-side via RBAC in the SQL WHERE clause. The logged-in
            admin account can access GET/POST /api/v1/documents/* and
            /api/v1/admin/*.
          </p>
        </div>
      </main>
    </div>
  );
}
