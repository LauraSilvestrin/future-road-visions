import { Database, Download, FileJson, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { api, type DadosUtilizados, type ScopeType } from "@/lib/api";

interface Props {
  data: DadosUtilizados;
  escopo: ScopeType;
  alvo: string;
  uf?: string;
}

export function DataUsedPanel({ data, escopo, alvo, uf }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const fmt = (n: number) => n.toLocaleString("pt-BR");

  const download = async (formato: "csv" | "json") => {
    try {
      setBusy(formato);
      await api.downloadExport({ escopo, alvo, uf, formato });
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="rounded-2xl border border-border/60 bg-card/60 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-4">
        <div className="flex items-center gap-2">
          <Database className="size-4 text-primary" />
          <h3 className="font-display text-lg">Dados Utilizados nesta Análise</h3>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => download("csv")}
            disabled={busy !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs text-primary hover:bg-primary/20 disabled:opacity-50"
          >
            <FileSpreadsheet className="size-3.5" />
            {busy === "csv" ? "Baixando…" : "Baixar CSV"}
          </button>
          <button
            onClick={() => download("json")}
            disabled={busy !== null}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border/60 bg-surface/50 px-3 py-1.5 text-xs text-foreground hover:bg-surface/80 disabled:opacity-50"
          >
            <FileJson className="size-3.5" />
            {busy === "json" ? "Baixando…" : "JSON"}
          </button>
        </div>
      </header>

      <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <Item label="Total de registros" value={fmt(data.total_registros)} />
        <Item label="Período analisado" value={`${data.periodo.inicio} – ${data.periodo.fim}`} />
        <Item label="Fontes" value={data.fontes.join(" + ")} />
        <Item
          label="Filtros aplicados"
          value={`${data.filtros_aplicados.escopo} = ${data.filtros_aplicados.alvo}${data.filtros_aplicados.uf ? ` (${data.filtros_aplicados.uf})` : ""}`}
        />
        <Item label="Colunas utilizadas" value={data.colunas_utilizadas.join(", ")} />
        <Item
          label="Anos no treino dos modelos"
          value={data.anos_treino.length ? `${data.anos_treino[0]}–${data.anos_treino[data.anos_treino.length - 1]} (${data.anos_treino.length} anos)` : "—"}
        />
      </dl>

      {data.anos_excluidos_do_treino.length > 0 && (
        <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
          <strong>Anos excluídos do treino:</strong> {data.anos_excluidos_do_treino.join(", ")}.
          {data.motivo_exclusao ? ` ${data.motivo_exclusao}` : ""}
        </p>
      )}

      {Object.keys(data.resumo_estatistico).length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Resumo estatístico dos dados selecionados
          </h4>
          <table className="w-full text-xs">
            <thead className="border-b border-border/60 text-muted-foreground">
              <tr>
                <th className="px-2 py-1.5 text-left">Métrica</th>
                <th className="px-2 py-1.5 text-right">Soma</th>
                <th className="px-2 py-1.5 text-right">Média</th>
                <th className="px-2 py-1.5 text-right">Mediana</th>
                <th className="px-2 py-1.5 text-right">Mín</th>
                <th className="px-2 py-1.5 text-right">Máx</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.resumo_estatistico).map(([k, v]) => (
                <tr key={k} className="border-b border-border/30">
                  <td className="px-2 py-1.5 font-medium capitalize">{k}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmt(v.soma)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmt(v.media)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmt(v.mediana)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmt(v.min)}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{fmt(v.max)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.amostra.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
            <Download className="mr-1 inline size-3" />
            Pré-visualizar amostra dos registros ({data.amostra.length} primeiros)
          </summary>
          <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-border/60 bg-surface/40">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-surface/90 backdrop-blur">
                <tr className="text-muted-foreground">
                  {Object.keys(data.amostra[0]).map(k => (
                    <th key={k} className="px-2 py-1.5 text-left font-medium">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.amostra.map((row, i) => (
                  <tr key={i} className="border-t border-border/30">
                    {Object.values(row).map((v, j) => (
                      <td key={j} className="px-2 py-1 font-mono">{String(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium text-foreground">{value}</dd>
    </div>
  );
}
