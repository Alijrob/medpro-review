"use client";

import { SearchResponse } from "@/lib/types";
import ProviderCard from "./ProviderCard";
import styles from "./search.module.css";

interface SearchResultsProps {
  results: SearchResponse;
  onRequestReport: (npi: string) => void;
  requestingNpi?: string | null;
}

export default function SearchResults({
  results,
  onRequestReport,
  requestingNpi,
}: SearchResultsProps) {
  if (results.total === 0) {
    return (
      <div className={styles.empty} role="status">
        <p>No providers found. Try a different name or NPI.</p>
      </div>
    );
  }

  return (
    <div className={styles.results}>
      <p className={styles.resultCount} role="status">
        {results.total} result{results.total !== 1 ? "s" : ""} found
        {results.query ? ` for "${results.query}"` : ""}
      </p>
      <div className={styles.resultsList}>
        {results.hits.map((provider) => (
          <ProviderCard
            key={provider.npi}
            provider={provider}
            onRequestReport={onRequestReport}
            isRequesting={requestingNpi === provider.npi}
          />
        ))}
      </div>
    </div>
  );
}
