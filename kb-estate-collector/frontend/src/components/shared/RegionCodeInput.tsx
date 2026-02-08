import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { COMMON_REGIONS } from "@/lib/constants"

interface RegionCodeInputProps {
  onSubmit: (regionCode: string) => void
  loading?: boolean
  buttonLabel?: string
}

export default function RegionCodeInput({
  onSubmit,
  loading,
  buttonLabel = "실행",
}: RegionCodeInputProps) {
  const [code, setCode] = useState("")

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input
          placeholder="지역코드 (예: 11680)"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="w-48"
        />
        <Button
          onClick={() => code && onSubmit(code)}
          disabled={!code || loading}
          size="sm"
        >
          {loading ? "처리중..." : buttonLabel}
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(COMMON_REGIONS).map(([regionCode, name]) => (
          <button
            key={regionCode}
            onClick={() => {
              setCode(regionCode)
              onSubmit(regionCode)
            }}
            disabled={loading}
            className="rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
          >
            {name}
          </button>
        ))}
      </div>
    </div>
  )
}
