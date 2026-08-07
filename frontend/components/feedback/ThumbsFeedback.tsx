"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Send } from "lucide-react";

import { ApiError, submitFeedback } from "@/lib/api-client";

interface ThumbsFeedbackProps {
  responseId: string;
  token: string | null;
}

export default function ThumbsFeedback({ responseId, token }: ThumbsFeedbackProps) {
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === null || !token) return;

    setError(null);
    setIsSubmitting(true);
    try {
      await submitFeedback(
        {
          response_id: responseId,
          rating: rating as 1 | -1,
          comment: comment.trim() || undefined,
        },
        token,
      );
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // Auth expired mid-session — surface so page.tsx can clear session.
        setError("Session expired. Please sign in again.");
      } else {
        setError(err instanceof Error ? err.message : "Feedback failed");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="mt-4 text-sm text-muted-foreground">
        Thank you for your feedback!
      </div>
    );
  }

  return (
    <div className="mt-6 pt-4 border-t border-border">
      <p className="text-sm font-medium text-foreground mb-2">
        Was this helpful?
      </p>
      <div className="flex items-center gap-3 mb-3">
        <button
          type="button"
          onClick={() => setRating(1)}
          className={`flex items-center gap-1 min-h-11 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
            rating === 1
              ? "bg-green-100 text-green-800 border-green-300"
              : "hover:bg-muted border-border"
          }`}
        >
          <ThumbsUp aria-hidden="true" />
          Helpful
        </button>
        <button
          type="button"
          onClick={() => setRating(-1)}
          className={`flex items-center gap-1 min-h-11 px-3 py-1.5 text-sm rounded-lg border transition-colors ${
            rating === -1
              ? "bg-red-100 text-red-800 border-red-300"
              : "hover:bg-muted border-border"
          }`}
        >
          <ThumbsDown aria-hidden="true" />
          Not helpful
        </button>
      </div>

      {rating !== null && (
        <div className="flex items-end gap-2">
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Add a comment (optional)"
              rows={2}
              maxLength={500}
              aria-label="Comment (optional)"
              className="flex-1 px-3 py-2 text-sm border border-border rounded-lg focus:ring-2 focus:ring-primary outline-none resize-none"
            />
           <button
             type="button"
             onClick={handleSubmit}
             disabled={rating === null || isSubmitting}
             className="px-4 py-2 min-h-11 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors"
           >
            <Send aria-hidden="true" />
            {isSubmitting ? "Sending…" : "Send"}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
