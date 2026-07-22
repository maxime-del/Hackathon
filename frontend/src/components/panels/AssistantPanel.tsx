import { useState } from "react";
import { askQuestion, exportUrl } from "../../api";
import type { Dashboard } from "../../types";
import { Panel } from "../ui";
import { Icon } from "../icons/Icon";
import { BeaconMark } from "../icons/BeaconMark";

export function AssistantPanel({ dashboard }: { dashboard: Dashboard }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [openTrace, setOpenTrace] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setAsking(true);
    setAnswer(null);
    try {
      const a = await askQuestion(question);
      setAnswer(a);
    } catch (err) {
      setAnswer(err instanceof Error ? err.message : "Erreur inconnue.");
    } finally {
      setAsking(false);
    }
  }

  const traces: [string, string][] = [
    ["graph_agent", dashboard.narratives.graph],
    ["anomaly_agent", dashboard.narratives.anomaly],
    ["risk_agent", dashboard.narratives.risk],
    ["decider_agent (synthese finale)", dashboard.narratives.decider],
  ];

  return (
    <div className="grid grid-2">
      <div className="stack">
        <Panel
          title={
            <span className="phare-avatar">
              <BeaconMark size={18} />
              Resume de Phare
            </span>
          }
        >
          {!dashboard.llm_available && (
            <p className="text-muted" style={{ fontSize: 11.5, marginBottom: 8 }}>
              Cle API du modele non configuree — resume genere par gabarit deterministe, Phare fonctionne hors-ligne.
            </p>
          )}
          <p style={{ whiteSpace: "pre-wrap" }}>{dashboard.situation_summary}</p>
        </Panel>

        <Panel
          title={
            <span className="phare-avatar">
              <BeaconMark size={18} />
              Poser une question a Phare
            </span>
          }
        >
          <form onSubmit={submit} className="stack">
            <input
              className="text-input"
              placeholder="Ex: les clients peuvent-ils payer maintenant ?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button className="btn btn-primary" type="submit" disabled={asking} style={{ alignSelf: "flex-start" }}>
              {asking && <span className="spin" />}
              Demander a Phare
            </button>
          </form>
          {answer && <p className="phare-bubble" style={{ marginTop: 12, whiteSpace: "pre-wrap", fontSize: 12.5 }}>{answer}</p>}
        </Panel>

        <Panel title="Exporter le plan" icon="download">
          <a className="btn" href={exportUrl()} download>
            <Icon name="download" size={14} />
            Telecharger la checklist (Markdown)
          </a>
        </Panel>
      </div>

      <Panel title="Traces des agents specialises" icon="list">
        <p className="text-muted" style={{ fontSize: 11.5, marginBottom: 10 }}>
          Chaque specialiste ne recoit que les resultats des tools deterministes qui le concernent.
        </p>
        <div className="stack">
          {traces.map(([name, text]) => {
            const open = openTrace === name;
            return (
              <div key={name} className="panel">
                <button
                  className="panel-head"
                  style={{ width: "100%", cursor: "pointer", border: "none" }}
                  onClick={() => setOpenTrace(open ? null : name)}
                >
                  <span className="panel-title mono" style={{ textTransform: "none" }}>{name}</span>
                  <Icon name="chevron-down" size={13} style={{ transform: open ? "rotate(180deg)" : undefined }} />
                </button>
                {open && (
                  <div className="panel-body" style={{ fontSize: 12 }}>
                    {text}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}
