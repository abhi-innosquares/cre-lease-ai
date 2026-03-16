import { useCallback, useEffect, useState } from "react";
import { Building2, FileBarChart2, ShieldAlert, Sparkles } from "lucide-react";
import { Toaster } from "sonner";
import { getPortfolioAnalytics } from "./api";
import UploadCard from "./components/UploadCard";
import LeaseCard from "./components/LeaseCard";
import PortfolioCard from "./components/PortfolioCard";
import AnalyticsCard from "./components/AnalyticsCard";

import BatchResultsPanel from "./components/BatchResultsPanel";
import ProcessingStatusPanel from "./components/ProcessingStatusPanel";
import PortfolioChatPage from "./components/PortfolioChatPage";
import PortfolioAnalyticsPage from "./components/PortfolioAnalyticsPage";
import LeaseSearchPage from "./components/LeaseSearchPage";
import { Card, CardContent } from "@/components/ui/card";
import "./styles.css";

function App() {
  const [activePage, setActivePage] = useState("workspace");
  const [leaseData, setLeaseData] = useState(null);
  const [leaseId, setLeaseId] = useState(null);
  const [uploadedLeases, setUploadedLeases] = useState([]);
  const [portfolioAnalytics, setPortfolioAnalytics] = useState(null);
  const [analyticsRefreshToken, setAnalyticsRefreshToken] = useState(0);
  const [processingJobs, setProcessingJobs] = useState([]);
  const tenant =
    leaseData?.structured_data?.tenant_name ||
    leaseData?.structured_data?.parties?.tenantName ||
    "Pending";

  const refreshPortfolioAnalytics = () => {
    getPortfolioAnalytics()
      .then((res) => setPortfolioAnalytics(res.data))
      .catch(() => setPortfolioAnalytics(null));
  };

  useEffect(() => {
    refreshPortfolioAnalytics();
  }, []);

  const handleSelectLease = (lease) => {
    setLeaseData(lease);
    setLeaseId(lease.lease_id);
  };

  const handleProcessingStarted = (jobs) => {
    setProcessingJobs(jobs);
  };

  const handleAllJobsDone = useCallback(
    (results) => {
      if (!results.length) return;
      const firstLease = results[0];
      setLeaseData(firstLease);
      setLeaseId(firstLease.lease_id);
      setUploadedLeases(results);
      refreshPortfolioAnalytics();
      setAnalyticsRefreshToken((t) => t + 1);
      setProcessingJobs([]);
    },
     
    []
  );

  return (
    <>
    <Toaster position="top-right" richColors />
    <div className="min-h-screen xl:grid xl:h-screen xl:grid-cols-[280px_1fr] xl:overflow-hidden">
      <aside className="border-r border-slate-800 bg-slate-950 px-6 py-8 text-slate-100 xl:sticky xl:top-0 xl:h-screen xl:overflow-y-auto">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/20 text-cyan-300">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Lease AI</h2>
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Enterprise Suite</p>
          </div>
        </div>

        <div className="mt-10 space-y-2 text-sm">
          <button
            type="button"
            onClick={() => setActivePage("workspace")}
            className={`w-full cursor-pointer rounded-md px-3 py-2 text-left ${
              activePage === "workspace" ? "bg-slate-900 text-slate-100" : "text-slate-400"
            }`}
          >
            Workspace
          </button>
          <button
            type="button"
            onClick={() => setActivePage("chat")}
            className={`w-full cursor-pointer rounded-md px-3 py-2 text-left ${
              activePage === "chat" ? "bg-slate-900 text-slate-100" : "text-slate-400"
            }`}
          >
            Chat Assistant
          </button>
          <button
            type="button"
            onClick={() => setActivePage("analytics")}
            className={`w-full cursor-pointer rounded-md px-3 py-2 text-left ${
              activePage === "analytics" ? "bg-slate-900 text-slate-100" : "text-slate-400"
            }`}
          >
            Portfolio Analytics
          </button>
          <button
            type="button"
            onClick={() => setActivePage("lease-search")}
            className={`w-full cursor-pointer rounded-md px-3 py-2 text-left ${
              activePage === "lease-search" ? "bg-slate-900 text-slate-100" : "text-slate-400"
            }`}
          >
            Lease Search
          </button>
        </div>

        <div className="mt-10 rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <p className="text-xs font-medium uppercase tracking-widest text-slate-400">Current Tenant</p>
          <p className="mt-2 truncate text-sm font-semibold text-slate-100">{tenant}</p>
          <p className="mt-1 text-xs text-slate-400">Active Lease ID: {leaseId || "Not selected"}</p>
        </div>
      </aside>

      <main className="p-4 md:p-8 xl:h-screen xl:overflow-y-auto">
        {activePage === "workspace" && (
          <>
            <section className="mb-6 animate-fade-up">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Lease Intelligence Platform</h1>
                  <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                    Upload leases, extract structured data, and review lease-level insights.
                  </p>
                </div>
                <div className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                  Workspace
                </div>
              </div>
            </section>

            <section className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
              <Card className="enterprise-card animate-fade-up">
                <CardContent className="flex items-center justify-between p-5">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">Avg Renewal Risk</p>
                    <p className="mt-2 text-2xl font-semibold">
                      {portfolioAnalytics?.avg_renewal_risk_score ?? "-"}
                    </p>
                  </div>
                  <ShieldAlert className="h-5 w-5 text-amber-600" />
                </CardContent>
              </Card>
              <Card className="enterprise-card animate-fade-up">
                <CardContent className="flex items-center justify-between p-5">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">High Risk Leases</p>
                    <p className="mt-2 text-2xl font-semibold">
                      {portfolioAnalytics?.high_risk_leases ?? "-"}
                    </p>
                  </div>
                  <Sparkles className="h-5 w-5 text-cyan-600" />
                </CardContent>
              </Card>
              <Card className="enterprise-card animate-fade-up">
                <CardContent className="flex items-center justify-between p-5">
                  <div>
                    <p className="text-xs uppercase tracking-widest text-muted-foreground">Total Leases</p>
                    <p className="mt-2 text-2xl font-semibold">{portfolioAnalytics?.total_leases ?? "-"}</p>
                  </div>
                  <FileBarChart2 className="h-5 w-5 text-emerald-600" />
                </CardContent>
              </Card>
            </section>

            <section className="mb-6 animate-fade-up">
              <UploadCard onProcessingStarted={handleProcessingStarted} />
            </section>

            <ProcessingStatusPanel
              jobs={processingJobs}
              onAllJobsDone={handleAllJobsDone}
            />

            <BatchResultsPanel
              uploadedLeases={uploadedLeases}
              activeLeaseId={leaseId}
              onSelect={handleSelectLease}
            />

            {leaseData && (
              <section className="mb-6 animate-fade-up">
                <LeaseCard leaseData={leaseData} />
              </section>
            )}
          </>
        )}

        {activePage === "chat" && (
          <section className="animate-fade-up">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Portfolio Chat</h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  Interactive assistant for questions across all uploaded leases.
                </p>
              </div>
              <div className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                Chat Page
              </div>
            </div>
            <PortfolioChatPage />
          </section>
        )}

        {activePage === "analytics" && (
          <section className="animate-fade-up">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Portfolio Analytics</h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  All-lease analytics view with aggregate KPIs, expiration calendar, and detailed analytics rows.
                </p>
              </div>
              <div className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                Analytics Page
              </div>
            </div>
            <PortfolioAnalyticsPage />
            <section className="mt-6 animate-fade-up">
              <AnalyticsCard refreshToken={analyticsRefreshToken} />
            </section>
            <section className="mt-6 animate-fade-up">
              <PortfolioCard />
            </section>
          </section>
        )}

        {activePage === "lease-search" && (
          <section className="animate-fade-up">
            <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Lease Search</h1>
                <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                  Search leases by ID or tenant name and open the linked source document.
                </p>
              </div>
              <div className="rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                Search Page
              </div>
            </div>
            <LeaseSearchPage />
          </section>
        )}
      </main>
    </div>
    </>
  );
}

export default App;
