"use client";

import { Copy, Edit } from "lucide-react";

import { Button } from "@/components/ui/button";

interface UserActionsProps {
  text: string;
  onStartEdit?: () => void;
}

export default function UserActions({ text, onStartEdit }: UserActionsProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // ignore — clipboard may be unavailable
    }
  };

  return (
    <div className="mt-1 flex items-center gap-1">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="size-7 rounded-full p-0"
        onClick={handleCopy}
        aria-label="Copy message"
        title="Copy"
      >
        <Copy className="size-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="size-7 rounded-full p-0"
        aria-label="Edit message"
        title="Edit"
        onClick={onStartEdit}
      >
        <Edit className="size-3.5" />
      </Button>
    </div>
  );
}
