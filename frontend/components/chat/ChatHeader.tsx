"use client";

import { Menu, MoreVertical } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Orb } from "@/components/ui/orb";

interface ChatHeaderProps {
  conversationTitle?: string;
  knowledgeBase?: string;
  onNewChat?: () => void;
  onRename?: () => void;
  onExport?: () => void;
  onClear?: () => void;
  onMobileMenu?: () => void;
}

export default function ChatHeader({
  conversationTitle = "New conversation",
  knowledgeBase = "Mortgage Guidelines",
  onNewChat,
  onRename,
  onExport,
  onClear,
  onMobileMenu,
}: ChatHeaderProps) {
  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b border-border/60 bg-background/80 backdrop-blur-sm px-3 sm:px-4">
      {/* Left: mobile menu + title */}
      <div className="flex items-center gap-2 min-w-0">
        {onMobileMenu && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-8 md:hidden"
            onClick={onMobileMenu}
            aria-label="Open navigation"
          >
            <Menu className="size-4" />
          </Button>
        )}
        <div className="flex items-center gap-2.5">
          <span className="text-primary">
            <Orb className="size-5" agentState="listening" />
          </span>
          <h1 className="text-sm font-semibold text-foreground truncate max-w-[180px] sm:max-w-xs">
            {conversationTitle}
          </h1>
        </div>
      </div>

      {/* Center: KB indicator */}
      <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="size-1.5 rounded-full bg-success" />
        <span>{knowledgeBase}</span>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-1.5">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="hidden h-7 gap-1 text-xs font-medium sm:flex"
          onClick={onNewChat}
        >
          New chat
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label="More options"
            >
              <MoreVertical className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={onRename}>Rename</DropdownMenuItem>
            <DropdownMenuItem onSelect={onExport}>Export</DropdownMenuItem>
            <DropdownMenuItem
              variant="destructive"
              onSelect={onClear}
            >
              Clear conversation
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
