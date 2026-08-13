"use client"

import type { ComponentProps, HTMLAttributes, ReactNode } from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

export type MessageProps = HTMLAttributes<HTMLDivElement> & {
  from: "user" | "assistant"
  timestamp?: number
}

function formatTimestamp(ts: number): string {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ""
  return date.toLocaleString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  })
}

function UserAvatar() {
  return (
    <Avatar className="ring-border size-7 ring-1 shrink-0">
      <AvatarImage alt="" src="" />
      <AvatarFallback className="bg-primary/10 text-primary text-xs font-bold">
        ME
      </AvatarFallback>
    </Avatar>
  )
}

export const Message = ({
  className,
  from,
  timestamp,
  children,
  ...props
}: MessageProps) => {
  const isUser = from === "user"
  return (
    <div
      className={cn(
        "group/message relative flex w-full items-start gap-2.5 py-2.5",
        isUser ? "flex-row-reverse" : "flex-row",
        className
      )}
      data-sender={from}
      {...props}
    >
      {/* User avatar — assistant avatar is passed as child */}
      {isUser && <UserAvatar />}

      {children}

      {/* Timestamp — always visible */}
      {typeof timestamp === "number" && (
        <span className="text-[10px] text-muted-foreground/50 mt-px">
          {formatTimestamp(timestamp)}
        </span>
      )}
    </div>
  )
}

const messageContentVariants = cva(
  "flex flex-col gap-2 rounded-lg text-sm",
  {
    variants: {
      variant: {
        contained: [
          "max-w-[80%] px-4 py-3",
          "group-[.is-user]:bg-accent group-[.is-user]:text-accent-foreground",
          "group-[.is-assistant]:bg-muted/50 group-[.is-assistant]:text-foreground",
        ],
        flat: [
          "group-[.is-user]:max-w-[80%] group-[.is-user]:bg-accent group-[.is-user]:px-4 group-[.is-user]:py-3 group-[.is-user]:text-accent-foreground",
          "group-[.is-assistant]:text-foreground",
        ],
      },
    },
    defaultVariants: {
      variant: "contained",
    },
  }
)

export type MessageContentProps = HTMLAttributes<HTMLDivElement> &
  VariantProps<typeof messageContentVariants>

export const MessageContent = ({
  children,
  className,
  variant,
  ...props
}: MessageContentProps) => (
  <div className={cn(messageContentVariants({ variant, className }))} {...props}>
    {children}
  </div>
)

export type MessageAvatarProps = ComponentProps<typeof Avatar> & {
  src: string
  name?: string
  children?: ReactNode
}

export const MessageAvatar = ({
  src,
  name,
  children,
  className,
  ...props
}: MessageAvatarProps) => (
  <Avatar className={cn("ring-border size-8 ring-1", className)} {...props}>
    <AvatarImage alt="" className="mt-0 mb-0" src={src} />
    {children ?? (
      <AvatarFallback>{name?.slice(0, 2) || "ME"}</AvatarFallback>
    )}
  </Avatar>
)
