"use client";

import { useState } from "react";
import { Loader2, Lock, Mail, ShieldCheck } from "lucide-react";
import { login } from "@/lib/api-client";
import { Orb } from "@/components/ui/orb";

interface LoginFormProps {
  onSuccess: () => void;
}

export default function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password || isLoading) return;

    setIsLoading(true);
    setError(null);
    try {
      // Login sets the httpOnly session cookie server-side; we no longer
      // store any token in localStorage (Phase 1 hardening).
      const result = await login(email.trim(), password);
      if (!result.access_token) {
        setError("Login succeeded but returned no session — try again.");
        return;
      }
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden gradient-mesh-bg px-4">
      {/* Decorative blurred blobs */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-32 w-96 h-96 rounded-full"
        style={{
          background:
            "radial-gradient(circle, oklch(0.68 0.28 265 / 25%) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-32 w-96 h-96 rounded-full"
        style={{
          background:
            "radial-gradient(circle, oklch(0.60 0.22 290 / 20%) 0%, transparent 70%)",
          filter: "blur(60px)",
        }}
      />

      {/* Card */}
      <div className="relative z-10 w-full max-w-sm animate-fade-in animate-slide-up">
        {/* Glass panel */}
        <div className="glass rounded-2xl p-8 shadow-2xl shadow-black/40">
          {/* Brand */}
          <div className="flex flex-col items-center mb-8 gap-3">
            <div className="animate-float">
              <Orb className="size-14" />
            </div>
            <div className="animate-fade-in text-center">
              <h1 className="text-2xl font-bold tracking-tight gradient-brand-text">
                Hexta
              </h1>
              <p className="text-xs text-white/50 mt-0.5 font-medium tracking-widest uppercase">
                Mortgage Knowledge Assistant
              </p>
            </div>
          </div>

          {/* Form */}
          <form
            onSubmit={handleSubmit}
            className="space-y-4 animate-fade-in"
          >
            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="text-xs font-semibold text-white/60 uppercase tracking-wider"
              >
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-white/30" />
                <input
                  id="email"
                  type="email"
                  inputMode="email"
                  autoComplete="username"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@hexa.local"
                  disabled={isLoading}
                  required
                  className="
                    w-full h-11 rounded-xl pl-10 pr-4
                    bg-white/8 border border-white/12
                    text-white placeholder:text-white/25
                    text-sm font-medium
                    focus:outline-none focus:border-primary/70
                    focus:bg-white/12 input-glow
                    transition-all duration-200
                    disabled:opacity-50
                  "
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="text-xs font-semibold text-white/60 uppercase tracking-wider"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-white/30" />
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  disabled={isLoading}
                  required
                  className="
                    w-full h-11 rounded-xl pl-10 pr-4
                    bg-white/8 border border-white/12
                    text-white placeholder:text-white/25
                    text-sm font-medium
                    focus:outline-none focus:border-primary/70
                    focus:bg-white/12 input-glow
                    transition-all duration-200
                    disabled:opacity-50
                  "
                />
              </div>
            </div>

            {/* Error */}
            {error && (
              <div role="alert" className="animate-fade-in">
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading || !email.trim() || !password}
              className="
                group relative w-full h-11 rounded-xl mt-2
                gradient-brand text-white font-semibold text-sm
                transition-all duration-200
                hover:opacity-90 hover:shadow-lg hover:shadow-primary/30
                active:scale-[0.98]
                disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
                overflow-hidden
              "
            >
              {/* Shimmer on hover */}
              <span className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                style={{
                  background: "linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.15) 50%, transparent 70%)",
                }}
              />
              <span className="relative flex items-center justify-center gap-2">
                {isLoading ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <ShieldCheck className="size-4 opacity-80" />
                )}
                {isLoading ? "Signing in…" : "Sign in"}
              </span>
            </button>
          </form>

          {/* Footer note */}
          <p className="text-center text-[11px] text-white/25 mt-6 animate-fade-in">
            Access restricted to authorized personnel only
          </p>
        </div>
      </div>
    </div>
  );
}