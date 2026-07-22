import { useState } from "react";
import type { Dashboard, Step } from "../../types";
import { ConfidenceBadge, Panel, RiskBadge } from "../ui";
import { Icon } from "../icons/Icon";

function StepRow({ s }: { s: Step }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="panel" style={{ borderColor: "var(--border)" }}>
      <div className="panel-body" style={{ display: "flex", gap: 12 }}>
        <span className="mono text-muted" style={{ fontSize: 12, paddingTop: 1 }}>
          {String(s.step).padStart(2, "0")}
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600 }}>{s.explain}</div>
          <div className="row" style={{ marginTop: 6, gap: 8 }}>
            <RiskBadge value={s.risk_level} />
            <ConfidenceBadge value={s.confidence} />
            <button
              className="btn"
              style={{ marginLeft: "auto", padding: "3px 9px", fontSize: 11 }}
              onClick={() => setOpen((o) => !o)}
            >
              Details techniques
              <Icon name="chevron-down" size={12} style={{ transform: open ? "rotate(180deg)" : undefined }} />
            </button>
          </div>
          {open && (
            <div className="text-muted" style={{ fontSize: 11.5, marginTop: 8, lineHeight: 1.6 }}>
              <div>
                Systeme : <span className="mono">{s.node}</span> — categorie : {s.category} — criticite : {s.criticality}
              </div>
              <div style={{ marginTop: 4 }}>Raisons de la confiance affichee :</div>
              <ul style={{ margin: "2px 0 0", paddingLeft: 18 }}>
                {s.confidence_reasons.map((r, i) => (
                  <li key={i}>
                    {r} <em>(source : {s.confidence_sources[i]})</em>
                  </li>
                ))}
              </ul>
              {s.prerequisites.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  Doit etre restaure apres :{" "}
                  {s.prerequisites.map((p) => (
                    <span key={p} className="mono">
                      {p}{" "}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function PlanPanel({ dashboard }: { dashboard: Dashboard }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div className="stack">
      <Panel
        title="Plan de redemarrage, dans l'ordre"
        icon="list"
        right={
          <button className="btn" style={{ padding: "3px 9px", fontSize: 11 }} onClick={() => setShowTable((v) => !v)}>
            {showTable ? "Masquer" : "Vue tableau"}
          </button>
        }
      >
        {showTable ? (
          <div style={{ overflowX: "auto" }}>
            <table className="data">
              <thead>
                <tr>
                  <th>Etape</th>
                  <th>Noeud</th>
                  <th>Categorie</th>
                  <th>Profondeur</th>
                  <th>Criticite</th>
                  <th>Confiance</th>
                  <th>Risque</th>
                  <th>Prerequis</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.steps.map((s) => (
                  <tr key={s.step}>
                    <td className="mono">{s.step}</td>
                    <td className="mono">{s.node}</td>
                    <td>{s.category}</td>
                    <td className="mono">{s.depth}</td>
                    <td>{s.criticality}</td>
                    <td>{s.confidence}</td>
                    <td>{s.risk_level}</td>
                    <td>{s.prerequisites.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="stack">
            {dashboard.steps.map((s) => (
              <StepRow key={s.step} s={s} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
