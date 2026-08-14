// Client-side session management (cookie-based).
// The JWT lives in an httpOnly cookie set by the backend (see
// backend/app/auth/cookies.py). JS cannot read it — localStorage is not
// used, so an XSS payload gets nothing. The frontend learns the session
// by calling /auth/verify, which reads the cookie server-side.

import { logout, verifyToken } from './api-client';

export interface UserSession {
  userId: number;
  email: string;
  role: string;
}

// In-memory cache only — deliberately NOT persisted to localStorage.
let cachedSession: UserSession | null = null;

/** Refresh the in-memory session by asking the backend to verify its cookie. */
export async function getSession(): Promise<UserSession | null> {
  try {
    const result = await verifyToken();
    if (!result.valid || result.user_id == null) {
      cachedSession = null;
      return null;
    }
    cachedSession = {
      userId: result.user_id,
      email: result.email ?? '',
      role: result.role ?? 'user',
    };
    return cachedSession;
  } catch {
    cachedSession = null;
    return null;
  }
}

/** Return the already-fetched session, or null if unknown yet/absent. */
export function getCachedSession(): UserSession | null {
  return cachedSession;
}

/**
 * Set the cached session after a successful login response.
 * The cookie itself was already set by the server; we only cache identity
 * that the /auth/verify endpoint would have returned.
 */
export function setSessionFromLogin(userId: number, email: string, role: string): void {
  cachedSession = { userId, email, role };
}

/** Drop the in-memory session. Server-side cookie clearing happens via /auth/logout. */
export function clearSession(): void {
  cachedSession = null;
}

/** Revoke the server-side session and drop the cached copy. */
export async function signOut(): Promise<void> {
  try {
    await logout();
  } catch {
    /* server cookie cleared on next login failure path; drop cache anyway */
  }
  clearSession();
}

// Backward-compatible shims for callers that still reference the old
// synchronous token API. With cookie transport there is no readable token,
// so these return based on session presence only.

export function getToken(): string | null {
  return cachedSession ? 'session-active' : null;
}

export function storeToken(token: string): void {
  // no-op — the token lives in the httpOnly cookie, never in JS storage.
  void token;
}

export function isTokenExpired(token: string | null): boolean {
  // Token expiry is enforced server-side; the shim mirrors "session known".
  return !token;
}