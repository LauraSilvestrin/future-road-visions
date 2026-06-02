import { TrendingDown, TrendingUp, Minus } from "lucide-react";

export function StatCard({
  label, value, delta, sub,
}: { label: string; value: string; delta?: number; sub?: string }) {
  const Icon = delta == null ? Minus : delta >= 0 ? TrendingUp : TrendingDown;
  const tone = delta == null ? "text-muted-foreground"
    : delta >= 0 ? "text-accent" : "text-success";
  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-5 shadow-card">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-2 font-display text-3xl">{value}</div>
      <div className={`mt-1 flex items-center gap-1 text-xs ${tone}`}>
        <Icon className="size-3.5" />
        {delta != null && <span>{delta >= 0 ? "+" : ""}{delta.toFixed(2)}% a.a.</span>}
        {sub && <span className="text-muted-foreground">· {sub}</span>}
      </div>
    </div>
  );
}
