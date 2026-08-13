"use client";

import { Copy, Edit } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface UserActionsProps {
  text: string;
  onStartEdit?: () => void;
}

export default function UserActions({ text, onStartEdit }: UserActionsProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard may be unavailable */
    }
  };

  return (
    <div
      className={cn(
        "mt-1.5 flex items-center gap-0.5 opacity-0",
        "group-hover/message:opacity-100 transition-opacity duration-200",
        "ml-auto"
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="size-6 rounded-full p-0"
        onClick={handleCopy}
        aria-label="Copy message"
        title="Copy"
      >
        <Copy className="size-3" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="size-6 rounded-full p-0"
        aria-label="Edit message"
        title="Edit"
        onClick={onStartEdit}
      >
        <Edit className="size-3" />
      </Button>
    </div>
  );
}
