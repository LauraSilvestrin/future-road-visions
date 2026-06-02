import type { ForecastResponse } from "@/lib/api";

export function RankingList({ ranking }: { ranking: NonNullable<ForecastResponse["ranking"]> }) {
  if (!ranking?.length) return null;
  const max = Math.max(...ranking.map(r => r.valor));
  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-5 shadow-card">
      <h3 className="mb-3 text-base font-semibold">Ranking comparativo</h3>
      <ul className="space-y-2">
        {ranking.map((r, i) => (
          <li key={r.nome} className="space-y-1">
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-mono text-xs text-muted-foreground w-6">{String(i + 1).padStart(2, "0")}</span>
              <span className="flex-1 truncate px-2">{r.nome}</span>
              <span className="font-mono text-foreground">{Math.round(r.valor).toLocaleString("pt-BR")}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface">
              <div className="h-full rounded-full bg-primary" style={{ width: `${(r.valor / max) * 100}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
