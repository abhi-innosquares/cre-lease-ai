import { useEffect, useState } from "react";
import { getPortfolio } from "../api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function PortfolioCard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    getPortfolio().then((res) => setData(res.data));
  }, []);

  if (!data) return null;

  return (
    <Card className="enterprise-card">
      <CardHeader>
        <CardTitle>Portfolio Summary</CardTitle>
        <CardDescription>Cross-lease financial and risk posture indicators.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-white/60 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Total Leases</p>
          <p className="mt-2 text-2xl font-semibold">{data.total_leases}</p>
        </div>
        <div className="rounded-lg border bg-white/60 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Average Rent</p>
          <p className="mt-2 text-2xl font-semibold">{data.average_rent_display ?? "—"}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {data.source_currencies?.length > 1
              ? `Normalized from ${data.source_currencies.join(", ")} into ${data.average_rent_currency}`
              : `Portfolio basis: ${data.average_rent_currency ?? "—"}`}
          </p>
        </div>
        <div className="rounded-lg border bg-white/60 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">High Risk Leases</p>
          <p className="mt-2 text-2xl font-semibold">{data.high_risk_leases}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default PortfolioCard;
