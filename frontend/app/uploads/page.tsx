"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  RefreshCw,
  Upload,
  X,
} from "lucide-react";

import Sidebar from "@/components/ui/sidebar";
import LoginForm from "@/components/auth/LoginForm";
import { clearToken, getToken, isTokenExpired } from "@/lib/auth";
import {
  DocumentItem,
  listDocuments,
  uploadDocument,
  ApiError,
} from "@/lib/api-client";

const ACCEPTED = ".pdf,.docx,.txt";
const ACCEPTED_MIME = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];
const MAX_MB = 20;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatusBadge({ approved }: { approved: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        approved
          ? "bg-green-500/10 text-green-500"
          : "bg-amber-500/10 text-amber-500"
      }`}
    >
      <span
        className={`size-1.5 rounded-full ${approved ? "bg-green-500" : "bg-amber-500"}`}
      />
      {approved ? "Approved" : "Pending"}
    </span>
  );
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`shimmer rounded-lg ${className}`} />;
}

export default function UploadsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Drag-and-drop state
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  useEffect(() => {
    const t = getToken();
    if (t && !isTokenExpired(t)) {
      setToken(t);
    } else {
      clearToken();
    }
    setAuthChecked(true);
  }, []);

  const fetchDocs = useCallback(() => {
    if (!token) return;
    setDocsLoading(true);
    setDocsError(null);
    listDocuments(token)
      .then((r) => setDocs(r.documents))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 403) {
          setDocsError("Admin access required to view documents.");
        } else {
          setDocsError(
            err instanceof Error ? err.message : "Failed to load documents"
          );
        }
      })
      .finally(() => setDocsLoading(false));
  }, [token]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleFileDrop = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    if (!ACCEPTED_MIME.includes(file.type)) {
      setUploadResult({
        type: "error",
        message: `Unsupported file type: ${file.type || file.name}. Use PDF, DOCX, or TXT.`,
      });
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setUploadResult({
        type: "error",
        message: `File too large (${formatBytes(file.size)}). Max is ${MAX_MB} MB.`,
      });
      return;
    }
    setSelectedFile(file);
    setUploadResult(null);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current++;
    setDragging(true);
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setDragging(false);
  };
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setDragging(false);
    handleFileDrop(e.dataTransfer.files);
  };

  const handleUpload = async () => {
    if (!selectedFile || !token || uploading) return;
    setUploading(true);
    setUploadProgress(10);
    setUploadResult(null);

    // Fake progress ticks while the request is in-flight
    const progressInterval = setInterval(() => {
      setUploadProgress((p) => Math.min(p + 10, 80));
    }, 200);

    try {
      const res = await uploadDocument(selectedFile, token);
      clearInterval(progressInterval);
      setUploadProgress(100);
      setTimeout(() => {
        setUploadProgress(0);
        setSelectedFile(null);
        fetchDocs();
      }, 800);
      setUploadResult({
        type: "success",
        message: `${res.filename} uploaded (${formatBytes(res.size_bytes)}) and queued for ingestion.`,
      });
    } catch (err) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setUploadResult({
        type: "error",
        message:
          err instanceof Error ? err.message : "Upload failed",
      });
    } finally {
      setUploading(false);
    }
  };

  if (!authChecked) return null;
  if (!token)
    return <LoginForm onSuccess={() => setToken(getToken())} />;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-y-auto scrollbar">
        <div className="max-w-4xl mx-auto px-6 py-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="flex items-center gap-3 mb-1">
              <div className="flex size-9 items-center justify-center rounded-xl gradient-brand">
                <Upload className="size-5 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-foreground">
                Document Upload
              </h1>
            </div>
            <p className="text-sm text-muted-foreground ml-12">
              Upload PDFs, DOCX, or TXT files. Documents are validated and
              queued for the batch ingestion pipeline — ingestion never runs
              in the request path.
            </p>
          </motion.div>

          {/* Drop Zone */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.35 }}
            className="mb-6"
          >
            <div
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => !selectedFile && inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
              }}
              aria-label="Document drop zone"
              className={`
                relative flex flex-col items-center justify-center gap-3
                rounded-2xl border-2 border-dashed p-10
                transition-all duration-200 cursor-pointer
                focus-visible:ring-2 focus-visible:ring-ring outline-none
                ${
                  dragging
                    ? "border-primary bg-primary/5 scale-[1.01]"
                    : selectedFile
                    ? "border-green-500/50 bg-green-500/5"
                    : "border-border/60 bg-card hover:border-primary/40 hover:bg-primary/5"
                }
              `}
            >
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPTED}
                className="hidden"
                onChange={(e) => handleFileDrop(e.target.files)}
              />

              {selectedFile ? (
                <div className="flex flex-col items-center gap-2 text-center">
                  <div className="flex size-12 items-center justify-center rounded-xl bg-green-500/10">
                    <FileText className="size-6 text-green-500" />
                  </div>
                  <p className="font-medium text-foreground text-sm">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatBytes(selectedFile.size)}
                  </p>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedFile(null);
                    }}
                    className="mt-1 flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive transition-colors"
                  >
                    <X className="size-3" /> Remove
                  </button>
                </div>
              ) : (
                <>
                  <div
                    className={`flex size-14 items-center justify-center rounded-2xl transition-colors ${
                      dragging ? "gradient-brand" : "bg-muted/60"
                    }`}
                  >
                    <Upload
                      className={`size-6 ${dragging ? "text-white" : "text-muted-foreground"}`}
                    />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-foreground">
                      Drop a file here, or{" "}
                      <span className="text-primary underline underline-offset-2">
                        browse
                      </span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      PDF, DOCX, TXT — max {MAX_MB} MB
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Progress bar */}
            <AnimatePresence>
              {uploadProgress > 0 && (
                <motion.div
                  initial={{ opacity: 0, scaleX: 0 }}
                  animate={{ opacity: 1, scaleX: 1 }}
                  exit={{ opacity: 0 }}
                  className="mt-3 h-1.5 rounded-full bg-muted overflow-hidden"
                >
                  <motion.div
                    className="h-full rounded-full gradient-brand"
                    initial={{ width: "0%" }}
                    animate={{ width: `${uploadProgress}%` }}
                    transition={{ duration: 0.2 }}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Result toast */}
            <AnimatePresence>
              {uploadResult && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className={`mt-3 flex items-start gap-2.5 rounded-xl border p-3 text-sm ${
                    uploadResult.type === "success"
                      ? "border-green-500/20 bg-green-500/5 text-green-600 dark:text-green-400"
                      : "border-destructive/20 bg-destructive/5 text-destructive"
                  }`}
                >
                  {uploadResult.type === "success" ? (
                    <CheckCircle2 className="size-4 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="size-4 shrink-0 mt-0.5" />
                  )}
                  <p>{uploadResult.message}</p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Upload button */}
            {selectedFile && (
              <motion.button
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                type="button"
                onClick={handleUpload}
                disabled={uploading}
                className="
                  mt-4 w-full rounded-xl gradient-brand
                  py-2.5 text-sm font-semibold text-white
                  hover:opacity-90 active:scale-[0.98] transition-all
                  disabled:opacity-60 disabled:cursor-not-allowed
                  flex items-center justify-center gap-2
                "
              >
                {uploading ? (
                  <>
                    <RefreshCw className="size-4 animate-spin" /> Uploading…
                  </>
                ) : (
                  <>
                    <Upload className="size-4" /> Upload Document
                  </>
                )}
              </motion.button>
            )}
          </motion.div>

          {/* Documents list */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.35 }}
            className="rounded-2xl border border-border/60 bg-card overflow-hidden"
          >
            <div className="px-6 py-4 border-b border-border/50 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">
                Uploaded Documents
              </h2>
              <button
                type="button"
                onClick={fetchDocs}
                disabled={docsLoading}
                aria-label="Refresh list"
                className="text-muted-foreground hover:text-foreground transition-colors disabled:opacity-40"
              >
                <RefreshCw
                  className={`size-4 ${docsLoading ? "animate-spin" : ""}`}
                />
              </button>
            </div>

            {docsError ? (
              <div className="p-6 flex items-start gap-2.5 text-sm text-destructive">
                <AlertTriangle className="size-4 shrink-0 mt-0.5" />
                <p>{docsError}</p>
              </div>
            ) : docsLoading ? (
              <div className="p-6 space-y-3">
                {[...Array(3)].map((_, i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : docs.length === 0 ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No documents uploaded yet.
              </div>
            ) : (
              <div className="divide-y divide-border/40">
                {docs.map((d, i) => (
                  <motion.div
                    key={d.id}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="flex items-center justify-between px-6 py-3.5 hover:bg-muted/20 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted/60">
                        <FileText className="size-4 text-muted-foreground" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-sm text-foreground truncate">
                          {d.title}
                        </p>
                        <p className="text-[10px] text-muted-foreground mt-0.5">
                          {d.doc_type.toUpperCase()} ·{" "}
                          {d.department || "All departments"} · v
                          {d.version}
                        </p>
                      </div>
                    </div>
                    <StatusBadge approved={d.is_approved} />
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </main>
    </div>
  );
}
