import { ServerCrash } from "lucide-react";

export function ApiSetupNotice({ error }: { error?: string }) {
  return (
    <div className="rounded-2xl border border-warning/40 bg-warning/5 p-6">
      <div className="mb-2 flex items-center gap-2 text-warning">
        <ServerCrash className="size-5" />
        <h3 className="font-semibold">Backend não conectado</h3>
      </div>
      <p className="text-sm text-muted-foreground">
        O dashboard precisa do backend FastAPI rodando (com Prophet, ARIMA, Random Forest e XGBoost)
        para gerar projeções a partir dos CSVs em <code className="font-mono text-foreground">/data</code>.
      </p>
      <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
        <li>Veja a pasta <code className="font-mono text-foreground">backend/</code> deste projeto.</li>
        <li>Hospede em Render / Railway / Fly.io / VPS: <code className="font-mono">pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000</code>.</li>
        <li>Coloque os 5 CSVs em <code className="font-mono text-foreground">backend/data/</code>.</li>
        <li>Configure a variável <code className="font-mono text-foreground">VITE_API_URL</code> apontando para a URL pública do backend e recarregue.</li>
      </ol>
      {error && <p className="mt-3 font-mono text-xs text-destructive">{error}</p>}
    </div>
  );
}
