import { useEffect, useMemo, useState } from "react";
import { getAllLeaseAnalytics } from "../api";
import { AlertTriangle, CalendarRange, Layers3, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function MetricTile({ label, value, icon }) {
  const Icon = icon;
  return (
    <div className="rounded-lg border bg-white/60 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">{label}</p>
        <Icon className="h-4 w-4 text-slate-500" />
      </div>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function PortfolioAnalyticsPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getAllLeaseAnalytics()
      .then((res) => {
        setData(res.data);
        setError("");
      })
      .catch(() => setError("Could not load portfolio analytics."));
  }, []);

  const topExpirations = useMemo(() => {
    if (!data?.expirations_by_month) return [];
    return data.expirations_by_month.slice(0, 8);
  }, [data]);

  if (error) {
    return (
      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Portfolio Analytics</CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Portfolio Analytics</CardTitle>
          <CardDescription>Loading full portfolio analytics...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Portfolio Analytics</CardTitle>
          <CardDescription>Portfolio-wide metrics across all uploaded leases.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="Total Leases" value={data.total_leases ?? 0} icon={Layers3} />
          <MetricTile label="Low Risk" value={data.risk_distribution?.low ?? 0} icon={ShieldCheck} />
          <MetricTile label="Medium Risk" value={data.risk_distribution?.medium ?? 0} icon={AlertTriangle} />
          <MetricTile label="High Risk" value={data.risk_distribution?.high ?? 0} icon={AlertTriangle} />
        </CardContent>
      </Card>

      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Lease Expiration Calendar</CardTitle>
          <CardDescription>Number of leases expiring by month.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {topExpirations.length ? (
            topExpirations.map((row) => (
              <div key={row.month} className="rounded-lg border bg-white/60 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">{row.month}</p>
                  <CalendarRange className="h-4 w-4 text-slate-500" />
                </div>
                <p className="mt-2 text-xl font-semibold">{row.count}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No expiration dates available.</p>
          )}
        </CardContent>
      </Card>

      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>All Lease Analytics</CardTitle>
          <CardDescription>Detailed analytics rows across the full portfolio.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-xs uppercase tracking-widest text-muted-foreground">
                  <th className="pb-2 text-left font-medium">Lease ID</th>
                  <th className="pb-2 text-left font-medium">Tenant</th>
                  <th className="pb-2 text-left font-medium">Region</th>
                  <th className="pb-2 text-left font-medium">Expiration</th>
                  <th className="pb-2 text-left font-medium">Base Rent</th>
                  <th className="pb-2 text-left font-medium">Normalized Rent</th>
                  <th className="pb-2 text-left font-medium">Eff Rent / SF</th>
                  <th className="pb-2 text-left font-medium">Risk</th>
                  <th className="pb-2 text-left font-medium">Renewal Option</th>
                  <th className="pb-2 text-left font-medium">Termination Option</th>
                </tr>
              </thead>
              <tbody>
                {(data.leases || []).map((lease) => (
                  <tr key={lease.lease_id} className="border-b text-slate-700 last:border-0">
                    <td className="py-3 pr-4 font-medium">{lease.lease_id}</td>
                    <td className="py-3 pr-4">{lease.tenant_name || "-"}</td>
                    <td className="py-3 pr-4">{lease.region || "-"}</td>
                    <td className="py-3 pr-4">{lease.expiration_date || "-"}</td>
                    <td className="py-3 pr-4">{lease.base_rent_display || "-"}</td>
                    <td className="py-3 pr-4">{lease.normalized_base_rent_display || "-"}</td>
                    <td className="py-3 pr-4">{lease.effective_rent_psf != null ? `${lease.effective_rent_psf} ${lease.effective_rent_psf_currency || ""}`.trim() : "-"}</td>
                    <td className="py-3 pr-4">{lease.renewal_risk_score ?? "-"}</td>
                    <td className="py-3 pr-4">{lease.has_renewal_option ?? "-"}</td>
                    <td className="py-3">{lease.has_termination_option ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default PortfolioAnalyticsPage;
