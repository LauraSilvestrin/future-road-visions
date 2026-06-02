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
  tipo: "historico" | "previsao";
}

export interface MetricForecast {
  metric: Metric;
  serie: ForecastPoint[];
  modelo_escolhido: string;
  comparacao_modelos: { modelo: string; mae: number; rmse: number; mape: number }[];
  taxa_crescimento_anual_pct: number;
  confiabilidade: "alta" | "media" | "baixa";
  confiabilidade_score: number; // 0..1
  observacoes: string[];
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
  gerado_em: string;
}

export interface OptionsResponse {
  ufs: string[];
  regioes: string[];
  municipios_por_uf: Record<string, string[]>;
  ano_min: number;
  ano_max: number;
}

export interface ForecastRequest {
  escopo: ScopeType;
  alvo: string;
  uf?: string;
  ano_inicio: number;
  ano_fim: number;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new Error(
      "API_URL não configurada. Defina VITE_API_URL com a URL do backend FastAPI.",
    );
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
  health: () => http<{ status: string; data_loaded: boolean }>("/api/health"),
};

export const isConfigured = () => Boolean(API_URL);
