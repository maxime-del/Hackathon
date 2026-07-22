import { useEffect, useState } from "react";
import { fetchDashboard } from "./api";
import type { Dashboard } from "./types";
import { Shell, type Page } from "./components/Shell";
import { UploadPage } from "./components/UploadPage";
import { DashboardPage } from "./components/DashboardPage";

export function App() {
  const [page, setPage] = useState<Page>("upload");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);

  useEffect(() => {
    fetchDashboard()
      .then((d) => {
        if (d) {
          setDashboard(d);
          setPage("dashboard");
        }
      })
      .catch(() => {
        /* pas de diagnostic en memoire au demarrage: reste sur le depot */
      });
  }, []);

  return (
    <Shell
      page={page}
      onNavigate={setPage}
      dashboardReady={dashboard !== null}
      llmAvailable={dashboard?.llm_available}
      processId={dashboard?.process_id}
    >
      {page === "upload" || !dashboard ? (
        <UploadPage
          onDiagnosed={(d) => {
            setDashboard(d);
            setPage("dashboard");
          }}
        />
      ) : (
        <DashboardPage dashboard={dashboard} />
      )}
    </Shell>
  );
}
