interface Props {
  data: { ano: number; categoria: string; valor: number }[];
  title: string;
}

export function Heatmap({ data, title }: Props) {
  if (!data?.length) return null;
  const anos = Array.from(new Set(data.map(d => d.ano))).sort((a, b) => a - b);
  const cats = Array.from(new Set(data.map(d => d.categoria)));
  const max = Math.max(...data.map(d => d.valor));
  const get = (a: number, c: string) => data.find(d => d.ano === a && d.categoria === c)?.valor ?? 0;

  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-5 shadow-card">
      <h3 className="mb-3 text-base font-semibold">{title}</h3>
      <div className="overflow-x-auto">
        <div className="inline-grid gap-px" style={{ gridTemplateColumns: `160px repeat(${anos.length}, 28px)` }}>
          <div />
          {anos.map(a => (
            <div key={a} className="text-center text-[10px] font-mono text-muted-foreground" style={{ writingMode: "vertical-rl" }}>{a}</div>
          ))}
          {cats.map(c => (
            <div key={c} className="contents">
              <div className="truncate pr-2 text-xs text-muted-foreground" title={c}>{c}</div>
              {anos.map(a => {
                const v = get(a, c);
                const intensity = max > 0 ? v / max : 0;
                return (
                  <div
                    key={`${c}-${a}`}
                    title={`${c} · ${a}: ${v.toLocaleString("pt-BR")}`}
                    className="h-6 w-7 rounded-sm"
                    style={{ background: `color-mix(in oklab, var(--color-primary) ${Math.round(intensity * 100)}%, var(--color-surface))` }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
