import { cn } from "@/lib/utils"
import { STATUS_VARIANT } from "@/lib/constants"

interface StatusBadgeProps {
  status: string
  label?: string
  className?: string
}

export default function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const variant = STATUS_VARIANT[status] || "bg-jb-bg-default text-jb-text-low"
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variant,
        className
      )}
    >
      {label || status}
    </span>
  )
}
