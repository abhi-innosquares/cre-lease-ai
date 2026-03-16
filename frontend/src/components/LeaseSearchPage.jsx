import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Search, ExternalLink } from "lucide-react";

import { getLeaseDocumentLink, searchLeases } from "../api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function LeaseSearchPage() {
  const [leaseIdInput, setLeaseIdInput] = useState("");
  const [tenantInput, setTenantInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [docLoadingLeaseId, setDocLoadingLeaseId] = useState(null);
  const [results, setResults] = useState([]);

  const hasFilters = useMemo(
    () => leaseIdInput.trim() || tenantInput.trim(),
    [leaseIdInput, tenantInput]
  );

  const runSearch = async () => {
    const leaseIdValue = leaseIdInput.trim();
    const tenantValue = tenantInput.trim();

    if (!leaseIdValue && !tenantValue) {
      toast.error("Enter at least one search filter", {
        description: "Use lease ID or tenant name to search leases.",
      });
      return;
    }

    const params = {};
    if (leaseIdValue) {
      const parsed = Number(leaseIdValue);
      if (!Number.isInteger(parsed) || parsed <= 0) {
        toast.error("Lease ID must be a positive whole number.");
        return;
      }
      params.lease_id = parsed;
    }
    if (tenantValue) params.tenant_name = tenantValue;

    try {
      setLoading(true);
      const res = await searchLeases(params);
      setResults(res.data?.leases || []);
    } catch (err) {
      console.error(err);
      toast.error("Search failed", {
        description: "Could not query lease records from backend.",
      });
    } finally {
      setLoading(false);
    }
  };

  const openDocument = async (leaseId) => {
    try {
      setDocLoadingLeaseId(leaseId);
      const res = await getLeaseDocumentLink(leaseId);
      const url = res.data?.url;
      if (!url) {
        toast.error("Document URL not available.");
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      console.error(err);
      toast.error("Could not open document", {
        description: err?.response?.data?.detail || "No linked source document found for this lease.",
      });
    } finally {
      setDocLoadingLeaseId(null);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Lease Search</CardTitle>
          <CardDescription>
            Search leases by lease ID or tenant name and open the linked source document.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-col gap-3 xl:flex-row xl:items-center"
            onSubmit={(e) => {
              e.preventDefault();
              runSearch();
            }}
          >
            <Input
              type="text"
              placeholder="Lease ID (example: 101)"
              value={leaseIdInput}
              onChange={(e) => setLeaseIdInput(e.target.value)}
              disabled={loading}
              className="xl:min-w-0 xl:flex-1"
            />
            <Input
              type="text"
              placeholder="Tenant name (example: NextGen)"
              value={tenantInput}
              onChange={(e) => setTenantInput(e.target.value)}
              disabled={loading}
              className="xl:min-w-0 xl:flex-1"
            />
            <div className="flex flex-wrap items-center gap-2 xl:flex-nowrap xl:self-stretch">
              <Button
                type="submit"
                disabled={loading || !hasFilters}
                className="min-w-[120px]"
              >
                <Search className="h-4 w-4" />
                {loading ? "Searching..." : "Search"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={loading}
                onClick={() => {
                  setLeaseIdInput("");
                  setTenantInput("");
                  setResults([]);
                }}
                className="min-w-[96px]"
              >
                Clear
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="enterprise-card">
        <CardHeader>
          <CardTitle>Search Results</CardTitle>
          <CardDescription>
            {results.length
              ? `${results.length} lease${results.length > 1 ? "s" : ""} found.`
              : "No results yet. Run a search above."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {results.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matching leases found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-widest text-muted-foreground">
                    <th className="pb-2 text-left font-medium">Lease ID</th>
                    <th className="pb-2 text-left font-medium">Tenant</th>
                    <th className="pb-2 text-left font-medium">File</th>
                    <th className="pb-2 text-left font-medium">Base Rent</th>
                    <th className="pb-2 text-left font-medium">Normalized Rent</th>
                    <th className="pb-2 text-left font-medium">Expiry</th>
                    <th className="pb-2 text-left font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((row) => (
                    <tr key={row.lease_id} className="border-b text-slate-700 last:border-0">
                      <td className="py-3 pr-4 font-medium">{row.lease_id}</td>
                      <td className="py-3 pr-4">{row.tenant_name || "-"}</td>
                      <td className="py-3 pr-4">{row.source_filename || "-"}</td>
                      <td className="py-3 pr-4">{row.base_rent_display || "-"}</td>
                      <td className="py-3 pr-4">{row.normalized_base_rent_display || "-"}</td>
                      <td className="py-3 pr-4">{row.expiration_date || "-"}</td>
                      <td className="py-3">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={!row.has_document || docLoadingLeaseId === row.lease_id}
                          onClick={() => openDocument(row.lease_id)}
                        >
                          <ExternalLink className="h-4 w-4" />
                          {docLoadingLeaseId === row.lease_id ? "Opening..." : "View Doc"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default LeaseSearchPage;
