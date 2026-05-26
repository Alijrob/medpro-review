"use client";

/**
 * Provider search page.
 *
 * Checks for Path B certification cookie. If not present, redirects to /certify.
 * Search results are fetched via TanStack Query -> /api/search (proxy).
 * Requesting a report calls POST /api/reports and navigates to /reports/{id}.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import SearchBar from "@/components/search/SearchBar";
import SearchResults from "@/components/search/SearchResults";
import UserProfile from "@/components/auth/UserProfile";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import { searchProviders, requestReport } from "@/lib/api";
import { SearchResponse, CERTIFICATION_COOKIE } from "@/lib/types";
import styles from "./search.module.css";

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState<string | null>(null);
  const [requestingNpi, setRequestingNpi] = useState<string | null>(null);

  // Path B gate: redirect to /certify if cookie not set
  useEffect(() => {
    const hasCert = document.cookie
      .split("; ")
      .some((c) => c.startsWith(`${CERTIFICATION_COOKIE}=`));
    if (!hasCert) {
      router.replace("/certify");
    }
  }, [router]);

  const { data, isLoading, isError, error, refetch } = useQuery<SearchResponse, Error>({
    queryKey: ["search", query],
    queryFn: () => searchProviders({ q: query ?? "" }) as Promise<SearchResponse>,
    enabled: query !== null && query.trim().length > 0,
    staleTime: 60_000,
  });

  async function handleRequestReport(npi: string) {
    setRequestingNpi(npi);
    try {
      const result = await requestReport(npi);
      router.push(`/reports/${result.report_id}`);
    } catch (err) {
      console.error("Failed to request report:", err);
      alert("Failed to request report. Please try again.");
      setRequestingNpi(null);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="/" className={styles.brand}>
          ResearchYourDoctor.com
        </a>
        <UserProfile />
      </header>

      <main className={styles.main}>
        <div className={styles.searchSection}>
          <h1 className={styles.title}>Search Providers</h1>
          <p className={styles.subtitle}>
            Enter a provider name or 10-digit NPI number
          </p>
          <SearchBar
            onSearch={(q) => setQuery(q)}
            isLoading={isLoading}
          />
        </div>

        <div className={styles.resultsSection}>
          {isLoading && <LoadingSpinner label="Searching..." />}

          {isError && (
            <ErrorMessage
              title="Search failed"
              message={error?.message ?? "Could not reach the search service."}
              onRetry={() => refetch()}
            />
          )}

          {!isLoading && !isError && data && (
            <SearchResults
              results={data}
              onRequestReport={handleRequestReport}
              requestingNpi={requestingNpi}
            />
          )}

          {!isLoading && !isError && !data && query !== null && (
            <p className={styles.hint}>No results yet.</p>
          )}

          {query === null && (
            <div className={styles.emptyState}>
              <p>Enter a provider name or NPI above to search.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
