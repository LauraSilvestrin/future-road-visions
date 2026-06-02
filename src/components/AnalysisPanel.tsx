import { FileText } from "lucide-react";

export function AnalysisPanel({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter(Boolean);
  return (
    <div className="rounded-2xl border bg-card bg-gradient-card p-6 shadow-card">
      <div className="mb-3 flex items-center gap-2">
        <FileText className="size-4 text-primary" />
        <h3 className="text-base font-semibold">Análise automática</h3>
      </div>
      <div className="space-y-3 text-sm leading-relaxed text-foreground/90">
        {blocks.map((b, i) => <p key={i}>{b}</p>)}
      </div>
    </div>
  );
}
