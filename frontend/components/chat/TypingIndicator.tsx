"use client";

import { cn } from "@/lib/utils";

interface TypingIndicatorProps {
  className?: string;
}

export default function TypingIndicator({ className }: TypingIndicatorProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 px-2 py-1.5",
        "text-muted-foreground text-xs",
        className
      )}
      aria-label="Assistant is typing"
    >
      <span className="typing-dot flex size-1.5 rounded-full bg-current" />
      <span className="typing-dot flex size-1.5 rounded-full bg-current" />
      <span className="typing-dot flex size-1.5 rounded-full bg-current" />
    </div>
  );
}
