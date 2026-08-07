"use client"

import type { ComponentProps, HTMLAttributes } from "react"
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
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
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
    <div className={cn("flex w-full flex-col", className)}>
      <div
        className={cn(
          "group flex w-full items-start gap-2 py-3",
          isUser
            ? "is-user justify-end"
            : "is-assistant flex-row-reverse justify-start"
        )}
        {...props}
      >
        {children}
      </div>
      {typeof timestamp === "number" && (
        <span
          className={cn(
            "select-none text-xs text-muted-foreground/70",
            isUser ? "text-right" : "pl-10"
          )}
        >
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
          "group-[.is-assistant]:bg-secondary group-[.is-assistant]:text-foreground",
        ],
        flat: [
          "group-[.is-user]:max-w-[80%] group-[.is-user]:bg-secondary group-[.is-user]:px-4 group-[.is-user]:py-3 group-[.is-user]:text-foreground",
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
  children?: React.ReactNode
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