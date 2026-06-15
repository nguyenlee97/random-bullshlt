import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-brand-500 text-white",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive text-destructive-foreground",
        outline: "text-foreground",
        green: "border-brand-200 bg-brand-50 text-brand-700",
        amber: "border-amber-100 bg-amber-50 text-amber-600",
        blue: "border-blue-200 bg-blue-50 text-blue-700",
        violet: "border-violet-200 bg-violet-50 text-violet-700",
        red: "border-red-200 bg-red-50 text-red-700",
        muted: "border-border bg-muted text-muted-foreground",
        "model-gemma": "border-violet-200 bg-violet-50 text-violet-700 gap-1",
        "model-qwen": "border-blue-200 bg-blue-50 text-blue-700 gap-1",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

function Badge({ className, variant, ...props }) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
