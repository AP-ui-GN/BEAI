import { compositionRows } from "@/lib/measurements"

export function CompositionChart({ value }: { value: unknown }) {
  const rows = compositionRows(value)
  const max = rows.reduce((highest, row) => Math.max(highest, row.count), 0)
  if (rows.length === 0) {
    return <p>No amino-acid composition was returned.</p>
  }
  return (
    <div className="space-y-2">
      <table className="w-full text-sm">
        <caption className="sr-only">Amino-acid composition from the analysis</caption>
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="py-1 font-medium">Residue</th>
            <th className="py-1 font-medium">Count</th>
            <th className="py-1 font-medium">Share of the largest count</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <th scope="row" className="py-1 text-left font-medium">
                {row.name}
              </th>
              <td className="mono py-1">{row.count}</td>
              <td className="py-1">
                <div className="bg-muted h-2 w-full rounded">
                  <div
                    className="h-2 rounded bg-primary"
                    style={{ width: max === 0 ? "0%" : `${(row.count / max) * 100}%` }}
                  />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
