import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, isConfigured, type ForecastRequest, type ForecastResponse } from "@/lib/api";
import { QueryPanel } from "@/components/QueryPanel";
import { ForecastChart } from "@/components/ForecastChart";
import { Heatmap } from "@/components/Heatmap";
import { RankingList } from "@/components/RankingList";
import { StatCard } from "@/components/StatCard";
import { AnalysisPanel } from "@/components/AnalysisPanel";
import { ApiSetupNotice } from "@/components/ApiSetupNotice";
import { Activity, ShieldAlert } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "RoadCast — Previsão de acidentes rodoviários com IA" },
      { name: "description", content: "Dashboard de séries temporais (Prophet, ARIMA, Random Forest, XGBoost) para projetar acidentes, mortos e feridos por município, UF e região." },
      { property: "og:title", content: "RoadCast — Previsão de acidentes rodoviários" },
      { property: "og:description", content: "Projeções estatísticas de acidentes rodoviários por município, UF e região." },
    ],
  }),
  component: Dashboard,
});

const CHART_COLORS = ["var(--color-chart-1)", "var(--color-chart-2)", "var(--color-chart-4)"];

function Dashboard() {
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    enabled: isConfigured(),
    retry: 0,
    refetchInterval: 30000,
  });

  const mutation = useMutation({
    mutationFn: (req: ForecastRequest) => api.forecast(req),
    onSuccess: setResult,
  });

  const apiReady = isConfigured() && health.data?.data_loaded;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border/60 bg-surface/40 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl bg-primary/15 text-primary shadow-glow">
              <Activity className="size-5" />
            </div>
            <div>
              <h1 className="font-display text-xl leading-tight">RoadCast</h1>
              <p className="text-xs text-muted-foreground">Previsão de acidentes rodoviários · 2007 – 2200</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className={`size-2 rounded-full ${apiReady ? "bg-success" : "bg-destructive"}`} />
            <span className="text-muted-foreground">
              {!isConfigured() ? "API não configurada" : health.data?.data_loaded ? "Backend online" : "Backend offline"}
            </span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="border-b border-border/60 bg-gradient-hero">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs text-primary">
              <ShieldAlert className="size-3.5" /> Séries temporais · Prophet · ARIMA · RF · XGBoost
            </span>
            <h2 className="mt-4 font-display text-4xl leading-tight md:text-5xl">
              Projeções estatísticas de acidentes,<br /> mortos e feridos no futuro.
            </h2>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Compare automaticamente quatro modelos de IA sobre dados históricos brasileiros e
              consulte projeções por <strong className="text-foreground">município</strong>,{" "}
              <strong className="text-foreground">UF</strong> ou{" "}
              <strong className="text-foreground">região</strong> — com intervalo de confiança
              e indicador explícito de confiabilidade.
            </p>
          </div>
        </div>
      </section>

      <main className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[380px_1fr]">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <QueryPanel onSubmit={mutation.mutate} loading={mutation.isPending} />
        </aside>

        <section className="space-y-6">
          {!isConfigured() && <ApiSetupNotice />}
          {isConfigured() && health.isError && (
            <ApiSetupNotice error={(health.error as Error).message} />
          )}
          {mutation.isError && (
            <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-5 text-sm text-destructive">
              {(mutation.error as Error).message}
            </div>
          )}

          {!result && !mutation.isPending && apiReady && (
            <EmptyState />
          )}

          {result && <Results data={result} />}
        </section>
      </main>

      <footer className="border-t border-border/60 py-6 text-center text-xs text-muted-foreground">
        Dados: histórico agregado 2007–2026 · Backend FastAPI em <code className="font-mono text-foreground">backend/</code>
      </footer>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-card/40 p-12 text-center">
      <h3 className="font-display text-xl">Pronto para projetar</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Escolha um escopo (município, UF ou região), defina o intervalo de anos e gere a previsão.
      </p>
      <div className="mt-6 grid gap-2 text-left text-sm text-muted-foreground sm:grid-cols-3">
        <Example title="Francisco Beltrão" subtitle="2075 → 2100" />
        <Example title="Paraná" subtitle="2030 → 2080" />
        <Example title="Região Sul" subtitle="próximos 50 anos" />
      </div>
    </div>
  );
}

function Example({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-surface/50 p-3">
      <div className="font-medium text-foreground">{title}</div>
      <div className="font-mono text-xs">{subtitle}</div>
    </div>
  );
}

function Results({ data }: { data: ForecastResponse }) {
  const splitYear = data.historico_max;
  const future = (m: (typeof data.metricas)[number]) =>
    m.serie.filter(p => p.tipo === "previsao");

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        {data.metricas.map(m => {
          const f = future(m);
          const last = f[f.length - 1];
          const label = m.metric.charAt(0).toUpperCase() + m.metric.slice(1);
          return (
            <StatCard
              key={m.metric}
              label={`${label} em ${last?.ano ?? "—"}`}
              value={last ? Math.round(last.valor).toLocaleString("pt-BR") : "—"}
              delta={m.taxa_crescimento_anual_pct}
              sub={`IC ${last ? Math.round(last.lower).toLocaleString("pt-BR") : "—"}–${last ? Math.round(last.upper).toLocaleString("pt-BR") : "—"}`}
            />
          );
        })}
      </div>

      <div className="rounded-xl border bg-card/60 px-4 py-3 text-xs text-muted-foreground">
        Escopo: <strong className="text-foreground">{data.escopo}</strong> · alvo:{" "}
        <strong className="text-foreground">{data.alvo}{data.uf ? ` (${data.uf})` : ""}</strong> ·
        histórico {data.historico_min}–{data.historico_max} · projeção {data.ano_inicio}–{data.ano_fim}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {data.metricas.map((m, i) => (
          <ForecastChart key={m.metric} data={m} splitYear={splitYear} color={CHART_COLORS[i % CHART_COLORS.length]} />
        ))}
      </div>

      <AnalysisPanel text={data.analise_textual} />

      <div className="grid gap-6 lg:grid-cols-2">
        {data.ranking && <RankingList ranking={data.ranking} />}
        {data.heatmap && <Heatmap data={data.heatmap} title="Mapa de calor — categorias × ano" />}
      </div>
    </>
  );
}
