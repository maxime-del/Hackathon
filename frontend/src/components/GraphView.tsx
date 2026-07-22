import { useMemo, useRef, useState } from "react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation } from "d3-force";
import type { GraphEdge, GraphNode } from "../types";

interface SimNode extends GraphNode {
  x: number;
  y: number;
}

const TONE_COLOR: Record<string, string> = {
  SUR: "var(--ok)",
  INCERTAIN: "var(--warn)",
  DANGER: "var(--danger)",
  INCONNU: "var(--neutral)",
};

const WIDTH = 900;
const HEIGHT = 520;

function useLayout(nodes: GraphNode[], edges: GraphEdge[]) {
  return useMemo(() => {
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n, x: 0, y: 0 }));
    const byId = new Map(simNodes.map((n) => [n.id, n]));
    const links = edges
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ source: e.source, target: e.target }));

    const sim = forceSimulation(simNodes as any)
      .force("charge", forceManyBody().strength(-260))
      .force("link", forceLink(links as any).id((d: any) => d.id).distance(95).strength(0.6))
      .force("center", forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", forceCollide(30))
      .stop();

    for (let i = 0; i < 260; i++) sim.tick();

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of simNodes) {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    }
    const pad = 50;
    const w = Math.max(1, maxX - minX);
    const h = Math.max(1, maxY - minY);
    const scale = Math.min((WIDTH - pad * 2) / w, (HEIGHT - pad * 2) / h, 1.4);
    for (const n of simNodes) {
      n.x = (n.x - minX) * scale + pad;
      n.y = (n.y - minY) * scale + pad;
    }

    return { nodes: simNodes, byId };
  }, [nodes, edges]);
}

export function GraphView({
  nodes,
  edges,
  highlightCategory,
  onSelectNode,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightCategory?: string | null;
  onSelectNode?: (id: string) => void;
}) {
  const { nodes: laidOut, byId } = useLayout(nodes, edges);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const dragging = useRef<{ x: number; y: number } | null>(null);

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    const delta = -e.deltaY * 0.001;
    setView((v) => ({ ...v, k: Math.min(2.5, Math.max(0.5, v.k + delta)) }));
  }
  function onMouseDown(e: React.MouseEvent) {
    dragging.current = { x: e.clientX - view.x, y: e.clientY - view.y };
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragging.current) return;
    setView((v) => ({ ...v, x: e.clientX - dragging.current!.x, y: e.clientY - dragging.current!.y }));
  }
  function endDrag() {
    dragging.current = null;
  }

  return (
    <div style={{ position: "relative" }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: HEIGHT, cursor: dragging.current ? "grabbing" : "grab", background: "var(--panel)" }}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
      >
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="var(--border-strong)" />
          </marker>
        </defs>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {edges.map((e, i) => {
            const s = byId.get(e.source);
            const t = byId.get(e.target);
            if (!s || !t) return null;
            return (
              <line
                key={i}
                x1={s.x}
                y1={s.y}
                x2={t.x}
                y2={t.y}
                stroke="var(--border-strong)"
                strokeWidth={1}
                markerEnd="url(#arrow)"
              />
            );
          })}
          {laidOut.map((n) => {
            const dimmed = highlightCategory ? n.category !== highlightCategory : false;
            return (
              <g
                key={n.id}
                transform={`translate(${n.x} ${n.y})`}
                opacity={dimmed ? 0.25 : 1}
                style={{ cursor: onSelectNode ? "pointer" : "default" }}
                onClick={() => onSelectNode?.(n.id)}
              >
                <circle r={9} fill={TONE_COLOR[n.confidence]} stroke="var(--panel)" strokeWidth={2} />
                <text
                  x={0}
                  y={20}
                  textAnchor="middle"
                  fontSize={9}
                  fontFamily="var(--font-mono)"
                  fill="var(--text-secondary)"
                >
                  {n.id.length > 12 ? n.id.slice(0, 11) + "…" : n.id}
                </text>
                <title>
                  {n.id} — {n.category} — confiance {n.confidence}
                </title>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="text-muted" style={{ position: "absolute", bottom: 8, left: 12, fontSize: 11 }}>
        Molette = zoom · glisser = deplacer
      </div>
    </div>
  );
}
