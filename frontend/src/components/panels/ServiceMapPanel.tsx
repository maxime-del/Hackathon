import { useState } from "react";
import type { Dashboard } from "../../types";
import { Panel, RiskBadge, toneOf } from "../ui";
import { GraphView } from "../GraphView";
import { Icon, type IconName } from "../icons/Icon";

export function ServiceMapPanel({ dashboard }: { dashboard: Dashboard }) {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedCard = dashboard.categories.find((c) => c.key === selected) ?? null;

  return (
    <div className="stack">
      <div
        className="grid"
        style={{ gridTemplateColumns: `repeat(${Math.min(dashboard.categories.length, 6)}, 1fr)` }}
      >
        {dashboard.categories.map((c) => {
          const active = selected === c.key;
          const tone = toneOf(c.status);
          return (
            <button
              key={c.key}
              onClick={() => setSelected(active ? null : c.key)}
              className="panel"
              style={{
                textAlign: "left",
                cursor: "pointer",
                padding: "12px 13px",
                borderColor: active ? "var(--accent)" : undefined,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div className="row" style={{ justifyContent: "space-between" }}>
                <Icon name={c.icon as IconName} size={17} style={{ color: "var(--text-secondary)" }} />
                <span className={`badge ${tone}`} />
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 600 }}>{c.label}</div>
              <div className="text-muted" style={{ fontSize: 11 }}>
                {c.count} element{c.count > 1 ? "s" : ""}
              </div>
            </button>
          );
        })}
      </div>

      {selectedCard && (
        <Panel title={`Detail — ${selectedCard.label}`} icon={selectedCard.icon as IconName}>
          {selectedCard.nodes.length === 0 ? (
            <p className="text-muted">Aucun element dans cette categorie pour ce processus.</p>
          ) : (
            <div className="stack">
              {selectedCard.nodes.map((n) => (
                <div key={n.node} className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12.5 }}>{n.human_name}</div>
                    <div className="text-muted" style={{ fontSize: 11.5 }}>
                      {n.risk_consequence}
                    </div>
                  </div>
                  <RiskBadge value={n.risk_level} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      )}

      <Panel title="Graphe de dependances" icon="network" tight>
        <GraphView
          nodes={dashboard.graph.nodes}
          edges={dashboard.graph.edges}
          highlightCategory={selected}
        />
      </Panel>

      {dashboard.broken_cycles.length > 0 && (
        <div className="badge danger" style={{ padding: "8px 12px", borderRadius: "var(--radius-sm)" }}>
          Cycles detectes et rompus pour permettre le tri : {dashboard.broken_cycles.map((c) => c.join(" ↔ ")).join(", ")}
        </div>
      )}
    </div>
  );
}
