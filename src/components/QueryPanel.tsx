import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, isConfigured, type ForecastRequest, type ScopeType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MapPin, Map, Globe2, Sparkles } from "lucide-react";

const REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"];

interface Props {
  onSubmit: (req: ForecastRequest) => void;
  loading?: boolean;
}

export function QueryPanel({ onSubmit, loading }: Props) {
  const [escopo, setEscopo] = useState<ScopeType>("municipio");
  const [uf, setUf] = useState<string>("PR");
  const [municipio, setMunicipio] = useState<string>("");
  const [regiao, setRegiao] = useState<string>("Sul");
  const [anoInicio, setAnoInicio] = useState<number>(2027);
  const [anoFim, setAnoFim] = useState<number>(2050);

  const { data: options } = useQuery({
    queryKey: ["options"],
    queryFn: api.options,
    enabled: isConfigured(),
    retry: 0,
  });

  useEffect(() => {
    if (options && !municipio && options.municipios_por_uf[uf]?.length) {
      setMunicipio(options.municipios_por_uf[uf][0]);
    }
  }, [options, uf, municipio]);

  const handle = () => {
    if (escopo === "municipio") {
      onSubmit({ escopo, alvo: municipio || "Francisco Beltrão", uf, ano_inicio: anoInicio, ano_fim: anoFim });
    } else if (escopo === "uf") {
      onSubmit({ escopo, alvo: uf, ano_inicio: anoInicio, ano_fim: anoFim });
    } else {
      onSubmit({ escopo, alvo: regiao, ano_inicio: anoInicio, ano_fim: anoFim });
    }
  };

  const ufs = options?.ufs ?? ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];
  const municipios = options?.municipios_por_uf[uf] ?? [];

  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-6 shadow-card">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Nova consulta</h2>
          <p className="text-sm text-muted-foreground">Projete acidentes, mortos e feridos no futuro.</p>
        </div>
        <Sparkles className="size-5 text-primary" />
      </div>

      <Tabs value={escopo} onValueChange={(v) => setEscopo(v as ScopeType)} className="mb-5">
        <TabsList className="grid w-full grid-cols-3 bg-surface">
          <TabsTrigger value="municipio" className="gap-2"><MapPin className="size-4" />Município</TabsTrigger>
          <TabsTrigger value="uf" className="gap-2"><Map className="size-4" />UF</TabsTrigger>
          <TabsTrigger value="regiao" className="gap-2"><Globe2 className="size-4" />Região</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="grid gap-4">
        {escopo === "municipio" && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">UF</Label>
              <Select value={uf} onValueChange={(v) => { setUf(v); setMunicipio(""); }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{ufs.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">Município</Label>
              {municipios.length > 0 ? (
                <Select value={municipio} onValueChange={setMunicipio}>
                  <SelectTrigger><SelectValue placeholder="Selecione" /></SelectTrigger>
                  <SelectContent className="max-h-64">
                    {municipios.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : (
                <Input value={municipio} onChange={e => setMunicipio(e.target.value)} placeholder="Francisco Beltrão" />
              )}
            </div>
          </div>
        )}

        {escopo === "uf" && (
          <div>
            <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">Estado</Label>
            <Select value={uf} onValueChange={setUf}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{ufs.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        )}

        {escopo === "regiao" && (
          <div>
            <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">Região</Label>
            <Select value={regiao} onValueChange={setRegiao}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{REGIOES.map(r => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">Ano início</Label>
            <Input type="number" value={anoInicio} onChange={e => setAnoInicio(+e.target.value)} min={2007} max={2200} />
          </div>
          <div>
            <Label className="mb-1.5 block text-xs uppercase tracking-wide text-muted-foreground">Ano fim</Label>
            <Input type="number" value={anoFim} onChange={e => setAnoFim(+e.target.value)} min={2007} max={2200} />
          </div>
        </div>

        <Button onClick={handle} disabled={loading} size="lg" className="mt-2 shadow-glow">
          {loading ? "Calculando projeção..." : "Gerar previsão"}
        </Button>
      </div>
    </div>
  );
}
