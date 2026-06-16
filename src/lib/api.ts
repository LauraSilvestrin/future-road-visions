// Cliente da API de previsão de acidentes rodoviários.
// Configure VITE_API_URL apontando para o backend FastAPI (ver pasta /backend).

export const API_URL =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export type ScopeType = "municipio" | "uf" | "regiao";
export type Metric = "acidentes" | "mortos" | "feridos";

export interface ForecastPoint {
  ano: number;
  valor: number;
  lower: number;
  upper: number;
  tipo: "historico" | "previsao" | "parcial";
}

export interface MetricForecast {
  metric: Metric;
  serie: ForecastPoint[];
  modelo_escolhido: string;
  comparacao_modelos: { modelo: string; mae: number; rmse: number; mape: number }[];
  taxa_crescimento_anual_pct: number;
  confiabilidade: "alta" | "media" | "baixa";
  confiabilidade_score: number;
  observacoes: string[];
  auditoria?: {
    metrica: string;
    coluna_origem?: string;
    historico_real_por_ano: { ano: number; valor: number }[];
    dados_treino: { ano: number; valor: number }[];
    previsao_bruta_ano_a_ano: { ano: number; valor_bruto: number }[];
    previsao_pos_processamento: { ano: number; valor_pos_processamento: number; motivo_valor_zerado?: string | null }[];
    valor_final_exibido?: { ano: number; valor: number; tipo: string }[];
    motivo_valor_zerado: Record<string, unknown>[];
    parametros_pos_processamento?: Record<string, number>;
  } | null;
}

export interface DadosUtilizados {
  total_registros: number;
  periodo: { inicio: number; fim: number };
  fontes: string[];
  filtros_aplicados: { escopo: string; alvo: string; uf?: string | null };
  colunas_utilizadas: string[];
  anos_excluidos_do_treino: number[];
  motivo_exclusao: string | null;
  anos_treino: number[];
  resumo_estatistico: Record<string, {
    soma: number; media: number; mediana: number; min: number; max: number;
  }>;
  mapeamento_colunas?: Record<string, string>;
  distribuicao_valores?: Record<string, {
    tipo_pandas: string;
    registros_validos: number;
    zeros: number;
    positivos: number;
    negativos: number;
    min: number;
    p25: number;
    mediana: number;
    media: number;
    p75: number;
    max: number;
    valores_mais_frequentes: { valor: number; frequencia: number }[];
  }>;
  amostra: Record<string, unknown>[];
}

export interface ForecastResponse {
  escopo: ScopeType;
  alvo: string;
  uf?: string;
  ano_inicio: number;
  ano_fim: number;
  historico_min: number;
  historico_max: number;
  metricas: MetricForecast[];
  analise_textual: string;
  ranking?: { nome: string; valor: number; metric: Metric }[];
  heatmap?: { ano: number; categoria: string; valor: number }[];
  dados_utilizados: DadosUtilizados;
  gerado_em: string;
}

export interface OptionsResponse {
  ufs: string[];
  regioes: string[];
  municipios_por_uf: Record<string, string[]>;
  ano_min: number;
  ano_max: number;
  ano_max_completo: number;
  anos_parciais: number[];
  fontes: string[];
}

export interface ForecastRequest {
  escopo: ScopeType;
  alvo: string;
  uf?: string;
  ano_inicio: number;
  ano_fim: number;
}

export interface ExportRequest {
  escopo: ScopeType;
  alvo: string;
  uf?: string;
  formato: "csv" | "json";
  amostra?: number;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new Error("API_URL não configurada. Defina VITE_API_URL com a URL do backend FastAPI.");
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Erro ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  options: () => http<OptionsResponse>("/api/options"),
  forecast: (body: ForecastRequest) =>
    http<ForecastResponse>("/api/forecast", { method: "POST", body: JSON.stringify(body) }),
  health: () => http<{ status: string; data_loaded: boolean; anos_parciais?: number[]; fontes?: string[] }>("/api/health"),
  exportUrl: () => `${API_URL}/api/export`,
  async downloadExport(req: ExportRequest) {
    if (!API_URL) throw new Error("API_URL não configurada.");
    const res = await fetch(`${API_URL}/api/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`Erro ${res.status}: ${await res.text()}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `roadcast_${req.escopo}_${req.alvo}.${req.formato}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

export const isConfigured = () => Boolean(API_URL);
