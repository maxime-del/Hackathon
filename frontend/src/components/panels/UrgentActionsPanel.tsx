import { useState } from "react";
import type { Dashboard } from "../../types";
import { Panel, RiskBadge, SeverityBadge } from "../ui";
import { Icon } from "../icons/Icon";

export function UrgentActionsPanel({ dashboard }: { dashboard: Dashboard }) {
  const highRisk = dashboard.steps.filter((s) => s.risk_level === "ELEVE");
  const [openFinding, setOpenFinding] = useState<string | null>(null);

  return (
    <div className="stack">
      <Panel title="A faire valider par un professionnel" icon="alert">
        {dashboard.manual_validations.length === 0 ? (
          <p className="badge ok" style={{ padding: "8px 12px", borderRadius: "var(--radius-sm)" }}>
            Aucune validation professionnelle bloquante identifiee.
          </p>
        ) : (
          <div className="stack">
            {dashboard.manual_validations.map((f) => (
              <div key={f.id} style={{ borderLeft: "3px solid var(--warn)", paddingLeft: 10 }}>
                <div style={{ fontWeight: 600, fontSize: 12.5 }}>{f.title_human}</div>
                <div className="text-secondary" style={{ fontSize: 12 }}>{f.action_pro}</div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Decisions a risque eleve, dans l'ordre du plan" icon="alert">
        {highRisk.length === 0 ? (
          <p className="text-muted">Aucune decision classee a risque eleve actuellement.</p>
        ) : (
          <div className="stack">
            {highRisk.map((s) => (
              <div key={s.step} className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 12.5 }}>
                    <span className="mono text-muted">#{s.step}</span> {s.human_name}
                  </div>
                  <div className="text-muted" style={{ fontSize: 11.5 }}>{s.risk_consequence}</div>
                </div>
                <RiskBadge value={s.risk_level} />
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel title={`Incoherences detectees dans les documents (${dashboard.findings.length})`} icon="search">
        <div className="stack">
          {dashboard.findings.map((f) => {
            const open = openFinding === f.id;
            return (
              <div key={f.id} className="panel" style={{ borderColor: "var(--border)" }}>
                <button
                  className="panel-head"
                  style={{ width: "100%", cursor: "pointer", border: "none", justifyContent: "flex-start", gap: 10 }}
                  onClick={() => setOpenFinding(open ? null : f.id)}
                >
                  <SeverityBadge value={f.severity} />
                  <span style={{ fontSize: 12.5, fontWeight: 600, textTransform: "none", letterSpacing: 0, color: "var(--text-primary)" }}>
                    {f.title_human}
                  </span>
                  <span style={{ marginLeft: "auto" }}>
                    <Icon name="chevron-down" size={14} style={{ transform: open ? "rotate(180deg)" : undefined }} />
                  </span>
                </button>
                {open && (
                  <div className="panel-body">
                    <p style={{ marginBottom: 8 }}>{f.detail_human}</p>
                    <hr className="rule" />
                    <p className="text-muted" style={{ fontSize: 11.5 }}>
                      <strong>Detail technique :</strong> {f.detail_tech}
                    </p>
                    <p className="text-muted" style={{ fontSize: 11.5 }}>
                      <strong>Sources :</strong> {f.sources.join(", ")}
                    </p>
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
