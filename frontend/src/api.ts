import type { ClassificationRow, Dashboard } from "./types";

export interface DiagnoseParams {
  message: string;
  siteVisible: boolean;
  canPay: boolean;
  incidentDt: string;
  csvFiles: File[];
  docxFiles: File[];
}

export interface DiagnoseResult {
  classification_report: ClassificationRow[];
  dashboard: Dashboard;
}

export async function runDiagnose(params: DiagnoseParams): Promise<DiagnoseResult> {
  const form = new FormData();
  form.set("message", params.message);
  form.set("site_visible", String(params.siteVisible));
  form.set("can_pay", String(params.canPay));
  form.set("incident_dt", params.incidentDt);
  for (const f of params.csvFiles) form.append("csv_files", f);
  for (const f of params.docxFiles) form.append("docx_files", f);

  const res = await fetch("/api/diagnose", { method: "POST", body: form });
  if (!res.ok) throw new Error(`Le diagnostic a echoue (HTTP ${res.status})`);
  return res.json();
}

export async function fetchDashboard(): Promise<Dashboard | null> {
  const res = await fetch("/api/dashboard");
  if (!res.ok) throw new Error(`Impossible de charger le dashboard (HTTP ${res.status})`);
  const data = await res.json();
  return data.dashboard;
}

export async function askQuestion(question: string): Promise<string> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`Le copilote n'a pas repondu (HTTP ${res.status})`);
  const data = await res.json();
  return data.answer;
}

export function exportUrl(): string {
  return "/api/export";
}
