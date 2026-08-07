// API client — calls FastAPI directly, no BFF proxy.
// JWT is stored client-side and sent per-request.

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

export interface SearchRequest {
  query: string;
}

export interface SearchExcerpt {
  text: string;
  source: {
    title: string;
    section: string | null;
    chunk_type: string;
  };
  confidence: number;
}

export interface SearchResponse {
  response_id: string;
  title: string;
  excerpts: SearchExcerpt[];
  confidence: number;
  routing: 'answer' | 'partial' | 'no_answer';
  related_questions: string[];
}

export interface AuthLoginRequest {
  email: string;
  password: string;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function searchKnowledgeBase(
  query: string,
  token?: string
): Promise<SearchResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}/search/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Search request failed',
      response.status
    );
  }

  return response.json();
}

export async function login(
  email: string,
  password: string
): Promise<AuthLoginResponse> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Login failed',
      response.status
    );
  }

  return response.json();
}

export async function verifyToken(
  token: string,
): Promise<{ valid: boolean; user_id?: number; email?: string }> {
  const response = await fetch(`${API_BASE_URL}/auth/verify`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    return { valid: false };
  }

  return response.json();
}

export interface FeedbackRequest {
  response_id: string;
  rating: 1 | -1;
  comment?: string;
}

export interface FeedbackResponse {
  message: string;
  feedback_id: number;
}

export async function submitFeedback(
  payload: FeedbackRequest,
  token: string,
): Promise<FeedbackResponse> {
  const response = await fetch(`${API_BASE_URL}/feedback/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Feedback submission failed',
      response.status,
    );
  }

  return response.json();
}

// --- Documents (admin-only; ingestion runs separately in the batch job) ---

export interface UploadResponse {
  message: string;
  filename: string;
  stored_as: string;
  size_bytes: number;
}

export interface DocumentItem {
  id: number;
  title: string;
  source_path: string;
  doc_type: string;
  department: string;
  is_active: boolean;
  is_approved: boolean;
  version: number;
  created_at: string;
}

export interface ListDocumentsResponse {
  documents: DocumentItem[];
}

export async function uploadDocument(
  file: File,
  token: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Upload failed',
      response.status,
    );
  }

  return response.json();
}

export async function listDocuments(
  token: string,
): Promise<ListDocumentsResponse> {
  const response = await fetch(`${API_BASE_URL}/documents/`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to load documents',
      response.status,
    );
  }

  return response.json();
}

// --- Analytics (admin-only) ---

export interface AnalyticsStats {
  total_queries: number;
  avg_confidence: number;
  answer_rate: number;
  daily_volume: { date: string; count: number }[];
}

export interface TopSource {
  title: string;
  citations: number;
}

export interface KnowledgeGap {
  id: number;
  query: string;
  intent: string | null;
  confidence: number;
  created_at: string;
}

export async function getAnalyticsStats(token: string): Promise<AnalyticsStats> {
  const response = await fetch(`${API_BASE_URL}/analytics/stats`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to load analytics stats',
      response.status,
    );
  }
  return response.json();
}

export async function getTopSources(token: string): Promise<{ top_sources: TopSource[] }> {
  const response = await fetch(`${API_BASE_URL}/analytics/top-sources`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to load top sources',
      response.status,
    );
  }
  return response.json();
}

export async function getKnowledgeGaps(token: string): Promise<{ knowledge_gaps: KnowledgeGap[] }> {
  const response = await fetch(`${API_BASE_URL}/analytics/knowledge-gaps`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to load knowledge gaps',
      response.status,
    );
  }
  return response.json();
}

// --- Admin (admin-only) ---

export interface UserItem {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  department: string | null;
  allowed_departments: string[];
  is_active: boolean;
  created_at: string;
}

export async function listUsers(token: string): Promise<{ users: UserItem[] }> {
  const response = await fetch(`${API_BASE_URL}/admin/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to load users',
      response.status,
    );
  }
  return response.json();
}

export async function patchUser(
  userId: number,
  patch: { is_active: boolean },
  token: string,
): Promise<{ id: number; email: string; is_active: boolean }> {
  const response = await fetch(`${API_BASE_URL}/admin/users/${userId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      (error && error.detail) || 'Failed to update user',
      response.status,
    );
  }
  return response.json();
}
