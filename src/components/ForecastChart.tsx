import {
  Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";
import type { MetricForecast } from "@/lib/api";

interface Props {
  data: MetricForecast;
  splitYear: number;
  color?: string;
}

const labelByMetric: Record<string, string> = {
  acidentes: "Acidentes",
  mortos: "Mortos",
  feridos: "Feridos",
};

export function ForecastChart({ data, splitYear, color = "var(--color-chart-1)" }: Props) {
  const rows = data.serie.map(p => ({
    ano: p.ano,
    historico: p.tipo === "historico" ? p.valor : null,
    previsao: p.tipo === "previsao" ? p.valor : null,
    banda: [p.lower, p.upper],
  }));

  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-5 shadow-card">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold">{labelByMetric[data.metric] ?? data.metric}</h3>
          <p className="text-xs text-muted-foreground">
            Modelo: <span className="font-mono text-foreground">{data.modelo_escolhido}</span>
            {" · "}Crescimento anual médio:{" "}
            <span className={data.taxa_crescimento_anual_pct >= 0 ? "text-accent" : "text-success"}>
              {data.taxa_crescimento_anual_pct >= 0 ? "+" : ""}{data.taxa_crescimento_anual_pct.toFixed(2)}%
            </span>
          </p>
        </div>
        <span className={
          "rounded-full border px-2 py-0.5 text-xs " +
          (data.confiabilidade === "alta" ? "border-success/40 text-success"
           : data.confiabilidade === "media" ? "border-warning/40 text-warning"
           : "border-destructive/40 text-destructive")
        }>
          Confiabilidade {data.confiabilidade} ({Math.round(data.confiabilidade_score * 100)}%)
        </span>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows} margin={{ top: 10, right: 12, bottom: 0, left: -8 }}>
          <defs>
            <linearGradient id={`band-${data.metric}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="ano" stroke="var(--color-muted-foreground)" fontSize={12} />
          <YAxis stroke="var(--color-muted-foreground)" fontSize={12} width={60} />
          <Tooltip
            contentStyle={{
              background: "var(--color-popover)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              fontSize: 12,
            }}
            formatter={(v: number | null) => (v == null ? "—" : Math.round(v).toLocaleString("pt-BR"))}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="banda" stroke="none" fill={`url(#band-${data.metric})`} name="Intervalo de confiança" />
          <Line type="monotone" dataKey="historico" stroke={color} strokeWidth={2.5} dot={false} name="Histórico" connectNulls={false} />
          <Line type="monotone" dataKey="previsao" stroke={color} strokeWidth={2.5} strokeDasharray="5 4" dot={false} name="Previsão" connectNulls={false} />
          <ReferenceLine x={splitYear} stroke="var(--color-muted-foreground)" strokeDasharray="2 4" label={{ value: "hoje", fill: "var(--color-muted-foreground)", fontSize: 10, position: "insideTopRight" }} />
        </ComposedChart>
      </ResponsiveContainer>

      {data.comparacao_modelos?.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-1.5 text-xs sm:grid-cols-4">
          {data.comparacao_modelos.map(m => (
            <div key={m.modelo} className={
              "rounded-lg border px-2 py-1.5 " +
              (m.modelo === data.modelo_escolhido ? "border-primary/50 bg-primary/5" : "border-border")
            }>
              <div className="font-mono text-[11px] text-muted-foreground">{m.modelo}</div>
              <div className="font-mono">MAPE {m.mape.toFixed(1)}%</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
