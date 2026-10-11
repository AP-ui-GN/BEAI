import { Badge } from "@/components/ui/badge"
import { originLabel } from "@/lib/labels"

export function OriginBadge({ origin }: { origin: string }) {
  return <Badge variant="outline">{originLabel(origin)}</Badge>
}
