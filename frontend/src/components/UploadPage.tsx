import { useState } from "react";
import { runDiagnose } from "../api";
import type { ClassificationRow, Dashboard } from "../types";
import { Panel } from "./ui";
import { Icon } from "./icons/Icon";
import { BeaconMark } from "./icons/BeaconMark";

function Dropzone({
  label,
  accept,
  files,
  onChange,
}: {
  label: string;
  accept: string;
  files: File[];
  onChange: (files: File[]) => void;
}) {
  return (
    <label className="dropzone" style={{ display: "block" }}>
      <input
        type="file"
        multiple
        accept={accept}
        onChange={(e) => onChange(Array.from(e.target.files ?? []))}
      />
      <Icon name="inbox" size={22} style={{ marginBottom: 6 }} />
      <div style={{ fontSize: 12.5, fontWeight: 600 }}>{label}</div>
      <div className="text-muted" style={{ fontSize: 11 }}>Cliquer pour choisir des fichiers ({accept})</div>
      {files.length > 0 && (
        <div className="file-chip-list">
          {files.map((f) => (
            <span key={f.name} className="file-chip">{f.name}</span>
          ))}
        </div>
      )}
    </label>
  );
}

export function UploadPage({ onDiagnosed }: { onDiagnosed: (dashboard: Dashboard) => void }) {
  const [csvFiles, setCsvFiles] = useState<File[]>([]);
  const [docxFiles, setDocxFiles] = useState<File[]>([]);
  const [incidentDt, setIncidentDt] = useState("2026-06-08 08:15");
  const [message, setMessage] = useState("Mon site de commandes ne marche plus, aide-moi a le redemarrer.");
  const [siteVisible, setSiteVisible] = useState(false);
  const [canPay, setCanPay] = useState(false);
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<ClassificationRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function launch() {
    setRunning(true);
    setError(null);
    try {
      const result = await runDiagnose({
        message,
        siteVisible,
        canPay,
        incidentDt,
        csvFiles,
        docxFiles,
      });
      setReport(result.classification_report);
      setDone(true);
      onDiagnosed(result.dashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="stack" style={{ maxWidth: 920 }}>
      <div className="hero">
        <div>
          <span className="hero-eyebrow">
            <BeaconMark size={16} pulse />
            SOS — Phare, votre copilote de reprise
          </span>
          <h1 className="hero-title">On reprend la main, dans le bon ordre.</h1>
          <p className="hero-sub">
            Deposez ce que vous avez, decrivez le probleme avec vos mots : Phare traduit le diagnostic technique en
            plan d'action clair, priorise et chiffre — pense pour un dirigeant sans DSI.
          </p>
        </div>
        <div className="hero-case">
          <div className="hero-case-label">Cas de demonstration</div>
          <div className="hero-case-value">NovaRetail</div>
          <div className="text-muted" style={{ fontSize: 11, marginTop: 2 }}>Processus P01 — commandes e-commerce</div>
        </div>
      </div>

      <Panel
        title={
          <span className="step-head">
            <span className="step-badge">1</span>
            Deposez vos sources
          </span>
        }
      >
        <p className="text-muted" style={{ fontSize: 11.5, marginBottom: 10 }}>
          Exports CSV du SI et documents .docx (PRA, rapports, notes...) — noms de fichiers et de colonnes peuvent
          etre completement differents de l'exemple, Phare les reconnait automatiquement par similarite. Sans depot,
          la demo tourne sur le cas NovaRetail fourni.
        </p>
        <div className="grid grid-2">
          <Dropzone label="Exports CSV du SI" accept=".csv" files={csvFiles} onChange={setCsvFiles} />
          <Dropzone label="Documents (PRA, rapports, notes...)" accept=".docx" files={docxFiles} onChange={setDocxFiles} />
        </div>
        {csvFiles.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <label className="field-label">Date/heure de declaration de l'incident (sert au calcul des ecarts RPO)</label>
            <input className="text-input" value={incidentDt} onChange={(e) => setIncidentDt(e.target.value)} />
          </div>
        )}
      </Panel>

      <Panel
        title={
          <span className="step-head">
            <span className="step-badge">2</span>
            Decrivez le probleme
          </span>
        }
      >
        <div className="grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
          <div>
            <label className="field-label">Decrivez le probleme avec vos mots</label>
            <textarea className="textarea" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
          </div>
          <div className="stack" style={{ paddingTop: 22 }}>
            <label className="checkbox-row">
              <input type="checkbox" checked={siteVisible} onChange={(e) => setSiteVisible(e.target.checked)} />
              Les clients voient le site
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={canPay} onChange={(e) => setCanPay(e.target.checked)} />
              Les clients peuvent payer
            </label>
          </div>
        </div>
        <button className="btn btn-primary" style={{ marginTop: 14, width: "100%", justifyContent: "center" }} onClick={launch} disabled={running}>
          {running && <span className="spin" />}
          <Icon name="search" size={14} />
          {running ? "Phare analyse la situation..." : "Lancer le diagnostic"}
        </button>
        {error && <p style={{ color: "var(--danger)", fontSize: 12, marginTop: 8 }}>{error}</p>}
      </Panel>

      {report.length > 0 && (
        <Panel title="Reconnaissance des fichiers deposes" icon="search">
          <div className="stack">
            {report.map((r, i) => (
              <div key={i} className={`badge ${r.role ? "ok" : "warn"}`} style={{ padding: "6px 10px", borderRadius: "var(--radius-sm)", justifyContent: "flex-start" }}>
                {r.missing
                  ? `Role non couvert par vos fichiers : ${r.role}`
                  : r.role
                  ? `${r.filename} → reconnu comme ${r.role} (confiance ${Math.round((r.score ?? 0) * 100)}%)`
                  : `${r.filename} → non reconnu (meilleur score ${Math.round((r.score ?? 0) * 100)}%), ignore`}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {done && (
        <div className="badge ok" style={{ padding: "10px 14px", borderRadius: "var(--radius-sm)", fontSize: 12.5 }}>
          Diagnostic pret. Ouvrez le Dashboard dans le menu a gauche pour voir les resultats.
        </div>
      )}
    </div>
  );
}
