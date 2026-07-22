import { useState } from "react";
import type { Dashboard } from "../types";
import { StatCard } from "./ui";
import { Icon } from "./icons/Icon";
import { ServiceMapPanel } from "./panels/ServiceMapPanel";
import { UrgentActionsPanel } from "./panels/UrgentActionsPanel";
import { PlanPanel } from "./panels/PlanPanel";
import { AssistantPanel } from "./panels/AssistantPanel";

const TABS = [
  { key: "map", label: "Cartographie", icon: "map" as const },
  { key: "actions", label: "Actions urgentes", icon: "alert" as const },
  { key: "plan", label: "Plan de reprise", icon: "list" as const },
  { key: "assistant", label: "Phare & export", icon: "chat" as const },
];

export function DashboardPage({ dashboard }: { dashboard: Dashboard }) {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("map");
  const risk = dashboard.risk.primary;

  return (
    <div>
      <div className="hero" style={{ marginBottom: 20 }}>
        <div>
          <span className="hero-eyebrow">Dossier {dashboard.process_id}</span>
          <h1 className="hero-title" style={{ fontSize: 21 }}>Dashboard de reprise</h1>
          <p className="hero-sub">
            Photographie de la situation au moment du diagnostic de Phare. Relancez un diagnostic depuis le depot des
            sources pour l'actualiser.
          </p>
        </div>
      </div>

      {risk && risk.data_sufficient ? (
        <div
          className="panel"
          style={{ borderColor: "var(--danger)", background: "var(--danger-soft)", padding: "12px 14px", marginBottom: 16, display: "flex", gap: 10 }}
        >
          <Icon name="alert" size={18} style={{ color: "var(--danger)", flexShrink: 0, marginTop: 1 }} />
          <div style={{ fontSize: 12.5 }}>
            <strong>Perte financiere estimee : {risk.estimated_loss_fmt}</strong> — actif le plus expose : <strong>{risk.asset}</strong>,
            {risk.last_reliable_backup && (
              <> derniere sauvegarde fiable le <strong>{new Date(risk.last_reliable_backup).toLocaleString("fr-FR")}</strong></>
            )}
            {risk.gap_hours != null && <> (~{risk.gap_hours.toFixed(0)}h avant l'incident)</>}. {risk.confidence_note}
            {dashboard.risk.others.length > 0 && (
              <div className="text-muted" style={{ marginTop: 4 }}>
                Autres actifs egalement en violation de RPO :{" "}
                {dashboard.risk.others.map((r) => `${r.asset} (${r.estimated_loss_fmt})`).join(", ")}
              </div>
            )}
          </div>
        </div>
      ) : risk ? (
        <div className="panel" style={{ padding: "10px 14px", marginBottom: 16, fontSize: 12.5 }}>{risk.confidence_note}</div>
      ) : null}

      <div className="kpi-row">
        <StatCard label="Etapes du plan" value={dashboard.kpis.steps} />
        <StatCard label="Etapes bloquantes" value={dashboard.kpis.blocking} tone={dashboard.kpis.blocking > 0 ? "warn" : undefined} />
        <StatCard label="Decisions a risque eleve" value={dashboard.kpis.high_risk} tone={dashboard.kpis.high_risk > 0 ? "danger" : "ok"} />
        <StatCard label="Anomalies critiques" value={dashboard.kpis.critical_findings} tone={dashboard.kpis.critical_findings > 0 ? "danger" : "ok"} />
        <StatCard label="Perte financiere" value={dashboard.kpis.estimated_loss_fmt} tone={risk?.data_sufficient ? "danger" : undefined} />
      </div>

      <p className="text-muted" style={{ fontSize: 11.5, marginBottom: 16 }}>
        Repartition du risque par decision : {dashboard.kpis.low_risk} faible · {dashboard.kpis.medium_risk} moyen · {dashboard.kpis.high_risk} eleve
      </p>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`tab${tab === t.key ? " active" : ""}`} onClick={() => setTab(t.key)}>
            <span className="row" style={{ gap: 6 }}>
              <Icon name={t.icon} size={13} />
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {tab === "map" && <ServiceMapPanel dashboard={dashboard} />}
      {tab === "actions" && <UrgentActionsPanel dashboard={dashboard} />}
      {tab === "plan" && <PlanPanel dashboard={dashboard} />}
      {tab === "assistant" && <AssistantPanel dashboard={dashboard} />}
    </div>
  );
}
