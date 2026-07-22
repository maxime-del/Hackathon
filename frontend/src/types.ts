export type Confidence = "SUR" | "INCERTAIN" | "DANGER" | "INCONNU";
export type RiskLevel = "FAIBLE" | "MOYEN" | "ELEVE";
export type Severity = "CRITIQUE" | "HAUTE" | "MOYENNE";

export interface Step {
  step: number;
  node: string;
  human_name: string;
  explain: string;
  category: string;
  depth: number;
  criticality: string;
  confidence: Confidence;
  confidence_reasons: string[];
  confidence_sources: string[];
  prerequisites: string[];
  dependents: string[];
  risk_level: RiskLevel;
  risk_consequence: string;
  linked_findings: string[];
}

export interface Finding {
  id: string;
  severity: Severity;
  title_tech: string;
  title_human: string;
  detail_tech: string;
  detail_human: string;
  sources: string[];
  action_pro: string | null;
  asset: string | null;
}

export interface RiskItem {
  asset: string;
  process_id: string;
  description: string;
  rpo_target: string | null;
  last_reliable_backup: string | null;
  gap_hours: number | null;
  eur_per_hour: number | null;
  estimated_loss_eur: number;
  estimated_loss_fmt: string;
  confidence_note: string;
  sources: string[];
  data_sufficient: boolean;
}

export interface GraphNode {
  id: string;
  category: string;
  confidence: Confidence;
  kind: string;
}
export interface GraphEdge {
  source: string;
  target: string;
  dependency_type: string;
}

export interface CategoryCardNode {
  node: string;
  human_name: string;
  risk_level: RiskLevel;
  risk_consequence: string;
}
export interface CategoryCard {
  key: string;
  label: string;
  icon: string;
  count: number;
  status: Confidence;
  nodes: CategoryCardNode[];
}

export interface Dashboard {
  process_id: string;
  situation_summary: string;
  llm_available: boolean;
  broken_cycles: string[][];
  risk: { primary: RiskItem | null; others: RiskItem[] };
  kpis: {
    steps: number;
    blocking: number;
    high_risk: number;
    medium_risk: number;
    low_risk: number;
    critical_findings: number;
    estimated_loss_fmt: string;
  };
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  categories: CategoryCard[];
  steps: Step[];
  findings: Finding[];
  manual_validations: Finding[];
  narratives: { graph: string; anomaly: string; risk: string; decider: string };
}

export interface ClassificationRow {
  filename: string | null;
  role: string | null;
  score: number | null;
  missing?: boolean;
}
