"use client";

import { useEffect, useState } from "react";
import { Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import {
  clearToken,
  getToken,
  isTokenExpired,
} from "@/lib/auth";
import {
  DocumentItem,
  ListDocumentsResponse,
  UploadResponse,
  listDocuments,
  uploadDocument,
} from "@/lib/api-client";

export default function UploadsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [docs, setDocs] = useState<DocumentItem[]>([]);

  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) setToken(t);
    else clearToken();
  }, []);

  useEffect(() => {
    if (!token) return;
    listDocuments(token)
      .then((r: ListDocumentsResponse) => setDocs(r.documents))
      .catch(() => null);
  }, [token]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.currentTarget as HTMLFormElement;
    const input = form.elements.namedItem("file") as HTMLInputElement | null;
    if (!input?.files?.[0]) return;
    setLoading(true);
    setStatus(null);
    try {
      const res: UploadResponse = await uploadDocument(
        input.files[0],
        token as string
      );
      setStatus(
        `${res.filename} uploaded (${res.size_bytes} bytes) and queued for ingestion.`
      );
      input.value = "";
    } catch (err: unknown) {
      setStatus(`Upload failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  if (!token) return <LoginForm onSuccess={() => setToken(getToken())} />;

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-6">
          <h1 className="text-2xl font-bold mb-1">Document uploads</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Upload PDFs, DOCX, or TXT. Files are validated and written to
            storage/pending/ for the batch ingestion pipeline (which runs
            separately — ingestion never runs in the request path).
          </p>
          <form onSubmit={handleUpload} className="flex gap-3 mb-6">
            <Input
              name="file"
              type="file"
              accept=".pdf,.doc,.docx,.txt"
              required
            />
            <Button type="submit" disabled={loading}>
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              Upload
            </Button>
          </form>
          {status && (
            <p className="text-sm text-muted-foreground mb-4">{status}</p>
          )}
          <h2 className="text-lg font-semibold mb-2">Uploaded documents</h2>
          <div className="space-y-2">
            {docs.map((d) => (
              <div
                key={d.id}
                className="border rounded p-3 text-sm flex items-center justify-between"
              >
                <span>
                  <span className="font-medium">{d.title}</span> ·{" "}
                  {d.doc_type} · {d.department || "—"}
                </span>
                <span className="text-xs text-muted-foreground">
                  {d.is_approved ? "approved" : "pending"} · v{d.version}
                </span>
              </div>
            ))}
            {docs.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No documents yet.
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
