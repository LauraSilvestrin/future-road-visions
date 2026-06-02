# RoadCast — Backend FastAPI

API de previsão de acidentes rodoviários com Prophet, ARIMA, Random Forest e XGBoost.

## Estrutura

```
backend/
  data/                         # coloque aqui os 5 CSVs
    municipio_ano.csv
    uf_ano.csv
    regiao_ano.csv
    causa_ano.csv
    clima_ano.csv
  main.py                       # FastAPI app
  data_loader.py                # leitura/normalização dos CSVs
  forecasting.py                # treino dos 4 modelos + escolha automática
  analysis.py                   # geração da análise textual em PT-BR
  requirements.txt
```

## Como rodar localmente

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# coloque os CSVs em backend/data/
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse `http://localhost:8000/api/health` para verificar.

## Deploy (Render / Railway / Fly.io)

Comando de build: `pip install -r requirements.txt`
Comando de start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

> **Importante:** Prophet pesa ~400 MB de dependências (cmdstanpy + numpy + pandas).
> Use planos com pelo menos 1 GB de memória. Em Render, escolha "Web Service".
> Suba a pasta `backend/data/` com os CSVs no repositório ou monte um volume.

Se quiser uma pasta de dados em outro local, defina `DATA_DIR=/caminho/dos/csvs`.

## Endpoints

- `GET /api/health` — status e contagem de anos disponíveis.
- `GET /api/options` — lista de UFs, regiões e municípios por UF.
- `POST /api/forecast` — corpo:
  ```json
  {
    "escopo": "municipio" | "uf" | "regiao",
    "alvo": "Francisco Beltrão" | "PR" | "Sul",
    "uf": "PR",                    // obrigatório só para escopo=municipio
    "ano_inicio": 2030,
    "ano_fim": 2080
  }
  ```

## Conectar ao frontend

No projeto Lovable, defina a variável de ambiente:

```
VITE_API_URL=https://sua-api.onrender.com
```

E recarregue o preview.

## Modelos

Cada métrica (`acidentes`, `mortos`, `feridos`) é projetada por todos os 4 modelos.
Os últimos ~25% dos anos (até 4 anos) viram conjunto de validação;
o modelo com **menor MAPE** vence e é re-treinado no histórico completo
antes da projeção final.

O intervalo de confiança (IC95%) é estimado a partir do desvio dos resíduos
históricos e **expande com √distância** ao último ano observado — projeções
muito distantes ficam explicitamente menos confiáveis, refletido no campo
`confiabilidade` (`alta`/`media`/`baixa`).
