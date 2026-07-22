import type { CSSProperties } from "react";

export type IconName =
  | "inbox"
  | "grid"
  | "map"
  | "alert"
  | "list"
  | "chat"
  | "download"
  | "refresh"
  | "search"
  | "chevron-down"
  | "identity"
  | "network"
  | "pki"
  | "vault"
  | "shield"
  | "backup"
  | "server"
  | "database"
  | "app"
  | "link"
  | "question";

const PATHS: Record<IconName, string> = {
  inbox:
    "M3 12h4l1.5 3h7L17 12h4M3 12l1.8-6.4A2 2 0 0 1 6.7 4h10.6a2 2 0 0 1 1.9 1.6L21 12M3 12v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  map: "M9 4 4 6.5v13L9 17l6 3 5-2.5v-13L15 7 9 4Zm0 0v13m6-10v13",
  alert: "M12 4 2.5 20h19L12 4Zm0 6.5v4.2M12 17.5h.01",
  list: "M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01",
  chat: "M4 5h16v11H8l-4 4V5Z",
  download: "M12 3v12m0 0-4-4m4 4 4-4M4 19h16",
  refresh: "M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 4v4h-4M6 20v-4h4",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm9 16-4.35-4.35",
  "chevron-down": "m6 9 6 6 6-6",
  identity: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 0 1 14 0",
  network: "M12 3v4M5 21v-4a3 3 0 0 1 3-3h8a3 3 0 0 1 3 3v4M9 21v-3M15 21v-3M12 7a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  pki: "M9 15a4 4 0 1 1 3.9-5H21v3h-2v3h-3v-3h-3.1A4 4 0 0 1 9 15Z",
  vault: "M4 5h16v14H4zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Zm0 3v2",
  shield: "M12 3.5 5 6v6c0 4.5 3 7.5 7 8.5 4-1 7-4 7-8.5V6l-7-2.5Z",
  backup: "M6.5 9a4.5 4.5 0 0 1 8.7-1.6A3.8 3.8 0 0 1 18 15H7a3.5 3.5 0 0 1-.5-6.9Z",
  server: "M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01",
  database: "M12 5c4.4 0 8-1.1 8-2.5S16.4 0 12 0 4 1.1 4 2.5 7.6 5 12 5Zm8 2.5c0 1.4-3.6 2.5-8 2.5S4 8.9 4 7.5M20 2.5v15c0 1.4-3.6 2.5-8 2.5S4 18.9 4 17.5v-15",
  app: "M5 4h6v6H5zM13 4h6v6h-6zM5 14h6v6H5zM13 14h6v6h-6z",
  link: "M9 15 15 9M8 13l-2.5 2.5a3.5 3.5 0 1 0 5 5L13 18M16 11l2.5-2.5a3.5 3.5 0 1 0-5-5L11 6",
  question: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-5.2v-.3c0-1 .6-1.6 1.3-2.1.8-.6 1.4-1.1 1.4-2.1 0-1.3-1.2-2.1-2.7-2.1-1.2 0-2.2.5-2.7 1.5M12 17.2h.01",
};

// Certaines icones (database) ont plusieurs sous-paths deja separes par
// espace dans une seule directive "d" - c'est valide en SVG (plusieurs
// sous-chemins "M..." concatenes), pas besoin de <path> multiples.

export function Icon({
  name,
  size = 16,
  style,
  strokeWidth = 1.7,
}: {
  name: IconName;
  size?: number;
  style?: CSSProperties;
  strokeWidth?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
