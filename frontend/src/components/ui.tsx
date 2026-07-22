import type { ReactNode } from "react";
import type { Confidence, RiskLevel, Severity } from "../types";
import { Icon, type IconName } from "./icons/Icon";

export function Panel({
  title,
  icon,
  right,
  tight,
  children,
}: {
  title?: ReactNode;
  icon?: IconName;
  right?: ReactNode;
  tight?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="panel">
      {title && (
        <div className="panel-head">
          <span className="panel-title">
            {icon && <Icon name={icon} size={13} />}
            {title}
          </span>
          {right}
        </div>
      )}
      <div className={`panel-body${tight ? " tight" : ""}`}>{children}</div>
    </div>
  );
}

const CONFIDENCE_TONE: Record<Confidence, "ok" | "warn" | "danger" | "neutral"> = {
  SUR: "ok",
  INCERTAIN: "warn",
  DANGER: "danger",
  INCONNU: "neutral",
};
const CONFIDENCE_LABEL: Record<Confidence, string> = {
  SUR: "Sauvegarde fiable",
  INCERTAIN: "A verifier",
  DANGER: "Danger",
  INCONNU: "Non documente",
};
const RISK_TONE: Record<RiskLevel, "ok" | "warn" | "danger"> = {
  FAIBLE: "ok",
  MOYEN: "warn",
  ELEVE: "danger",
};
const RISK_LABEL: Record<RiskLevel, string> = {
  FAIBLE: "Risque faible",
  MOYEN: "Risque moyen",
  ELEVE: "Risque eleve",
};
const SEVERITY_TONE: Record<Severity, "danger" | "warn" | "neutral"> = {
  CRITIQUE: "danger",
  HAUTE: "warn",
  MOYENNE: "neutral",
};

export function ConfidenceBadge({ value }: { value: Confidence }) {
  return <span className={`badge ${CONFIDENCE_TONE[value]}`}>{CONFIDENCE_LABEL[value]}</span>;
}
export function RiskBadge({ value }: { value: RiskLevel }) {
  return <span className={`badge ${RISK_TONE[value]}`}>{RISK_LABEL[value]}</span>;
}
export function SeverityBadge({ value }: { value: Severity }) {
  return <span className={`badge ${SEVERITY_TONE[value]}`}>{value}</span>;
}

export function toneOf(value: Confidence): "ok" | "warn" | "danger" | "neutral" {
  return CONFIDENCE_TONE[value];
}

export function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: "ok" | "warn" | "danger";
}) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value mono">{value}</div>
    </div>
  );
}
