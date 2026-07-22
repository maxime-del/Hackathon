import type { ReactNode } from "react";
import { Icon } from "./icons/Icon";
import { BeaconMark } from "./icons/BeaconMark";

export type Page = "upload" | "dashboard";

const NAV: { key: Page; label: string; hint: string; icon: "inbox" | "grid" }[] = [
  { key: "upload", label: "Depot des sources", hint: "Nouveau diagnostic", icon: "inbox" },
  { key: "dashboard", label: "Dashboard", hint: "Plan de reprise", icon: "grid" },
];

export function Shell({
  page,
  onNavigate,
  dashboardReady,
  llmAvailable,
  processId,
  children,
}: {
  page: Page;
  onNavigate: (p: Page) => void;
  dashboardReady: boolean;
  llmAvailable?: boolean;
  processId?: string;
  children: ReactNode;
}) {
  return (
    <div className="shell">
      <nav className="rail">
        <div className="brand">
          <BeaconMark size={30} />
          <div className="brand-word">
            <span className="brand-name">SOS</span>
            <span className="brand-tag">Cellule de reprise</span>
          </div>
        </div>

        <div className="nav-group">
          <span className="nav-eyebrow">Navigation</span>
          {NAV.map((n) => {
            const disabled = n.key === "dashboard" && !dashboardReady;
            const active = page === n.key;
            return (
              <button
                key={n.key}
                className={`nav-item${active ? " active" : ""}`}
                onClick={() => !disabled && onNavigate(n.key)}
                disabled={disabled}
              >
                <Icon name={n.icon} size={16} />
                <span className="nav-item-text">
                  <span className="nav-item-label">{n.label}</span>
                  <span className="nav-item-hint">{n.hint}</span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="rail-spacer" />

        <div className="rail-footer">
          {processId && (
            <div className="rail-case">
              <span className="rail-case-label">Dossier actif</span>
              <span className="rail-case-id mono">P{processId.replace(/^P/, "")}</span>
            </div>
          )}
          {llmAvailable !== undefined && (
            <div className="phare-status">
              <span className={`phare-dot${llmAvailable ? " on" : ""}`} />
              <span>
                <strong>Phare</strong> {llmAvailable ? "en ligne" : "hors-ligne"}
              </span>
            </div>
          )}
        </div>
      </nav>

      <div className="main">
        <header className="topbar">
          <div>
            <span className="topbar-eyebrow">{page === "upload" ? "Nouveau diagnostic" : "Vue d'ensemble"}</span>
            <h1 className="topbar-title">{page === "upload" ? "Depot des sources" : "Dashboard de reprise"}</h1>
          </div>
          <div className="topbar-spacer" />
          {processId && <span className="pill mono">P{processId.replace(/^P/, "")}</span>}
          {page === "dashboard" && (
            <button className="btn" onClick={() => onNavigate("upload")}>
              <Icon name="refresh" size={13} />
              Nouveau diagnostic
            </button>
          )}
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
