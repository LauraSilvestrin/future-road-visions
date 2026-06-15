# RoadCast — Relatório de Auditoria da Camada de Dados e Previsão

> Revisão completa após a migração da base **PRF-only** para **RENAEST + DATATRAN/PRF**.

## 1. Estrutura real dos CSVs atualmente no projeto

Inspeção direta dos arquivos em `backend/data/` (separador `;`, UTF-8):

| Arquivo | Linhas | Colunas | Período |
|---|---|---|---|
| `municipio_ano.csv` | 42.173 | `ano; uf; municipio; acidentes; mortos; feridos; pessoas` | 2018–2026 |
| `uf_ano.csv` | 224 | `ano; uf; acidentes; mortos; feridos; pessoas` | 2018–2026 |
| `regiao_ano.csv` | 45 | `ano; regiao; acidentes; mortos; feridos` | 2018–2026 |
| `causa_ano.csv` | 142 | `ano; causa_acidente; acidentes; mortos` | 2018–2026 |
| `clima_ano.csv` | 92 | `ano; condicao_metereologica; acidentes; mortos` | 2018–2026 |

### Totais nacionais por ano (acidentes)

| Ano | Total |
|---|---|
| 2018 | 749.157 |
| 2019 | 1.035.077 |
| 2020 | 932.550 |
| 2021 | 1.042.161 |
| 2022 | 1.109.497 |
| 2023 | 1.185.543 |
| 2024 | 1.155.843 |
| 2025 | 1.171.293 |
| **2026** | **85.760  ← parcial (coleta em andamento)** |

**Achado central:** o ano **2026 representa ~7%** do volume típico anual — claramente coleta parcial, e era o principal vetor das previsões absurdas.

---

## 2. Problemas identificados e correções

| # | Gráfico/Análise | Problema | Causa raiz | Correção aplicada | Métrica/comportamento atual |
|---|---|---|---|---|---|
| 1 | **Previsão de acidentes / mortos / feridos** (todos os escopos) | Tendência puxada artificialmente para zero | Ano 2026 parcial era incluído no treino, indicando "queda de 93%" | Detector de ano parcial em `data_loader._detectar_anos_parciais` (limite 60% da mediana dos 3 anos anteriores). Anos parciais são excluídos do treino dos modelos e marcados como `tipo: "parcial"` na série | Modelos treinam em **2018–2025**; 2026 exibido como ponto destacado, não influencia a tendência |
| 2 | **Projeções de longo prazo (RF / XGBoost)** | Valores explodiam ou colapsavam a zero em horizontes >20 anos | Features quadráticas `(ano - base)²` + ausência de damping | Removida a feature quadrática; mantida apenas tendência linear + log. Adicionado **damping exponencial** (0.85^dist) que mistura com média recente. Clip em `[0.4·min_hist, 2.5·max_hist]` | Projeções permanecem em ordem de grandeza realista mesmo até 2100 |
| 3 | **Schema `municipio_ano`** | Erro silencioso ao acessar coluna `veiculos` | Coluna existia no antigo schema PRF, foi removida no RENAEST | `_coerce_numeric` agora cobre apenas as colunas realmente presentes (`acidentes, mortos, feridos, pessoas`) | Sem mais NaN/zeros artificiais |
| 4 | **Ranking de municípios** | Ranking calculado via previsão modelo-a-modelo de cada município (instável, lento) | Cada município com poucos pontos gerava previsões erráticas | Substituído por **soma histórica observada** (excluindo anos parciais) — métrica robusta e auditável | Soma de acidentes 2018–2025, top 15 |
| 5 | **Heatmap de causas** | Incluía ano parcial 2026 distorcendo cores | Mesma raiz do problema 1 | Filtra `~ano.isin(anos_parciais)` antes de agregar | Visualização limpa |
| 6 | **Análise textual** | Mencionava "limitações dos dados PRF", "rodovias federais", horizonte 2007 | Texto herdado do escopo antigo | Reescrita: cita fontes reais (`RENAEST + DATATRAN/PRF`), tamanho efetivo da amostra, anos excluídos, motivo da exclusão | Cada análise começa com: *"Esta análise foi realizada com base em N registros entre A e B, oriundos de RENAEST + DATATRAN/PRF..."* |
| 7 | **Confiabilidade** | Penalidade só ficava "baixa" após 80 anos | Calibrada para horizontes muito longos | Recalibrada: penalidade plena em **>40 anos** de horizonte, peso maior em MAPE e horizonte | Indicadores `alta/media/baixa` agora coerentes com volume real de dados |
| 8 | **Headers/Footers UI** | Texto "2007 – 2200" e "histórico 2007–2026" | Premissa antiga | Atualizado para "RENAEST + DATATRAN/PRF" e período real | Reflete a base atual |
| 9 | **Histórico curto (<5 anos)** | Modelo extrapolava mesmo com 2-3 pontos | Sem guarda mínima | Quando há <5 anos úteis: **sem projeção**, apenas série observada, confiabilidade baixa explicitada | Não exibe gráficos zerados/artificiais |

---

## 3. Métricas que passaram a ser usadas

- **Holdout temporal:** últimos 1–3 anos (antes: até 4, frequentemente capturando o parcial)
- **Seleção de modelo:** menor MAPE entre `Prophet, ARIMA, RandomForest, XGBoost, Linear`
- **Banda de confiança:** `1.96 · σ_resíduos · (1 + √dist · 0.5)`, mínimo de 10% do valor
- **Confiabilidade global:** `0.45·MAPE + 0.40·penalidade_horizonte + 0.15·tamanho_histórico`
- **Ranking:** soma histórica observada (não previsão)

---

## 4. Rastreabilidade adicionada (novo)

Cada resposta de `/api/forecast` agora inclui `dados_utilizados` com:

- `total_registros` efetivamente filtrados
- `periodo` real (min/max dos anos)
- `fontes` (`["RENAEST", "DATATRAN/PRF"]`)
- `filtros_aplicados`
- `colunas_utilizadas`
- `anos_excluidos_do_treino` + `motivo_exclusao`
- `anos_treino`
- `resumo_estatistico` (soma, média, mediana, min, max por métrica)
- `amostra` (primeiros 50 registros)

No frontend, isso vira a seção **"Dados Utilizados nesta Análise"** com botões **Baixar CSV** / **JSON** (`POST /api/export`). O CSV inclui cabeçalho de metadados (`# _fonte`, `# _filtros`, `# _gerado_em`, etc.).

---

## 5. Arquivos alterados

- `backend/data_loader.py` — detecção de anos parciais, schema real, dataclass com `ano_max_completo`, `anos_parciais`, `fontes`
- `backend/forecasting.py` — exclusão de anos parciais, sem feature quadrática, damping, clip realista, gate de histórico mínimo
- `backend/main.py` — payload com `dados_utilizados`, novo endpoint `/api/export`, ranking por soma histórica
- `backend/analysis.py` — texto reescrito referenciando amostra e fontes
- `src/lib/api.ts` — novos types + helper `downloadExport`
- `src/components/DataUsedPanel.tsx` — **novo** painel com metadados, resumo e botões de export
- `src/components/ForecastChart.tsx` — suporte ao `tipo: "parcial"`
- `src/routes/index.tsx` — integra painel, header/footer atualizados

---

## 6. Como validar localmente

```bash
cd backend
pip install -r requirements.txt
python main.py
# em outro terminal
curl -X POST http://localhost:8000/api/forecast \
  -H 'Content-Type: application/json' \
  -d '{"escopo":"municipio","alvo":"PINGO DAGUA","uf":"MG","ano_inicio":2026,"ano_fim":2035}'
```

Verifique no payload:
- `dados_utilizados.anos_excluidos_do_treino` deve listar `2026`
- `analise_textual` deve começar com `"Esta análise foi realizada com base em N registros..."`
- Nenhuma projeção deve ser zero ou negativa
