import { Inbox } from "lucide-react"

interface EmptyStateProps {
  message?: string
}

export default function EmptyState({ message = "데이터가 없습니다" }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <Inbox className="mb-3 h-12 w-12" />
      <p className="text-sm">{message}</p>
    </div>
  )
}
