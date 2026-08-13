"use client";

import { useState } from "react";
import { ChevronDown, AlertTriangle, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import type { SearchExcerpt } from "@/lib/api-client";
import { cn } from "@/lib/utils";

interface ResponsePackageCardProps {
  excerpts: SearchExcerpt[];
  routing: "answer" | "partial" | "no_answer";
  sourcesOpen?: boolean;
}

export default function ResponsePackageCard({
  excerpts,
  routing,
  sourcesOpen,
}: ResponsePackageCardProps) {
  const [showAllExcerpts, setShowAllExcerpts] = useState(false);

  if (routing === "no_answer" || excerpts.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start gap-3 rounded-xl border border-warning/20 bg-warning/5 p-4"
      >
        <AlertTriangle className="size-4 text-warning shrink-0 mt-0.5" />
        <div>
          <p className="text-base font-medium text-foreground">
            No match found in knowledge base
          </p>
          <p className="text-sm text-muted-foreground mt-0.5">
            Try rephrasing your question or asking about a different topic.
          </p>
        </div>
      </motion.div>
    );
  }

  /** Deduplicate source documents by title */
  const documents = Array.from(
    excerpts
      .reduce((acc, e) => {
        if (!acc.has(e.source.title)) {
          acc.set(e.source.title, e.source.section);
        }
        return acc;
      }, new Map<string, string | null>())
      .entries()
  ).sort(([a], [b]) => a.localeCompare(b));

  /** The top excerpt is the primary answer; others are supporting evidence */
  const primary = excerpts[0];
  const supporting = excerpts.slice(1);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="w-full space-y-3"
    >
      {/* Primary answer excerpt */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.25 }}
        className="rounded-2xl border border-border/60 bg-card p-4"
      >
        <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
          {primary.text}
        </p>

        {/* Source label (small, muted, bottom of card) */}
        <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground/50">
          <FileText className="size-3" aria-hidden="true" />
          <span className="truncate">
            {primary.source.section || primary.source.title}
          </span>
          {primary.source.chunk_type && (
            <>
              <span aria-hidden="true">·</span>
              <span className="uppercase tracking-wider">
                {primary.source.chunk_type}
              </span>
            </>
          )}
        </div>
      </motion.div>

      {/* Supporting excerpts (collapsed by default) */}
      {supporting.length > 0 && (
        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {showAllExcerpts &&
              supporting.map((excerpt, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ delay: i * 0.04, duration: 0.2 }}
                  className="rounded-xl border border-border/50 bg-muted/30 p-3"
                >
                  <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
                    {excerpt.text}
                  </p>
                  <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground/40">
                    <FileText className="size-2.5" aria-hidden="true" />
                    <span className="truncate">
                      {excerpt.source.section || excerpt.source.title}
                    </span>
                  </div>
                </motion.div>
              ))}
          </AnimatePresence>

          <button
            type="button"
            onClick={() => setShowAllExcerpts((v) => !v)}
            aria-expanded={showAllExcerpts}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs text-muted-foreground",
              "hover:text-primary hover:bg-muted/60 transition-colors duration-150",
              "focus-visible:ring-2 focus-visible:ring-ring outline-none"
            )}
          >
            <ChevronDown
              className={cn(
                "size-3.5 transition-transform duration-200",
                showAllExcerpts && "rotate-180"
              )}
            />
            <span>
              {showAllExcerpts
                ? "Show fewer"
                : `${supporting.length} more excerpt${supporting.length === 1 ? "" : "s"}`}
            </span>
          </button>
        </div>
      )}

      {/* Sources panel */}
      <AnimatePresence>
        {sourcesOpen && (
          <motion.div
            key="sources"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            id="hexa-sources-list"
            role="region"
            aria-label="Sources"
            className="overflow-hidden"
          >
            <div className="rounded-xl border border-border/50 bg-muted/30 p-3 space-y-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-2">
                Sources ({documents.length})
              </p>
              {documents.map(([docTitle, section]) => (
                <div key={docTitle} className="flex items-start gap-2 text-sm">
                  <div className="size-5 shrink-0 mt-0.5 rounded bg-primary/10 flex items-center justify-center">
                    <FileText className="size-3 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <span className="font-medium text-foreground text-xs">
                      {docTitle}
                    </span>
                    {section && (
                      <p className="text-[10px] text-muted-foreground">
                        {section}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
