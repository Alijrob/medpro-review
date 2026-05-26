"use client";

import { ProviderSearchHit } from "@/lib/types";
import styles from "./search.module.css";

interface ProviderCardProps {
  provider: ProviderSearchHit;
  onRequestReport: (npi: string) => void;
  isRequesting?: boolean;
}

export default function ProviderCard({
  provider,
  onRequestReport,
  isRequesting = false,
}: ProviderCardProps) {
  const confidencePct = Math.round(provider.identity_confidence * 100);
  const hasExclusion = provider.exclusion_flag;

  return (
    <div
      className={`${styles.card} ${hasExclusion ? styles.cardExclusion : ""}`}
      data-testid="provider-card"
    >
      <div className={styles.cardHeader}>
        <div>
          <h3 className={styles.providerName}>{provider.name}</h3>
          <span className={styles.npi}>NPI: {provider.npi}</span>
        </div>
        {hasExclusion && (
          <span className={styles.exclusionBadge} aria-label="Federal exclusion flag">
            Exclusion Flag
          </span>
        )}
      </div>

      <div className={styles.cardMeta}>
        {provider.specialty_group && (
          <span className={styles.metaItem}>{provider.specialty_group}</span>
        )}
        {provider.primary_specialty && provider.primary_specialty !== provider.specialty_group && (
          <span className={styles.metaItem}>{provider.primary_specialty}</span>
        )}
        {provider.state && (
          <span className={styles.metaItem}>{provider.state}</span>
        )}
        <span
          className={`${styles.confidence} ${
            provider.identity_confidence >= 0.98
              ? styles.confidenceHigh
              : provider.identity_confidence >= 0.85
                ? styles.confidenceMed
                : styles.confidenceLow
          }`}
          title="Identity confidence score"
        >
          {confidencePct}% confidence
        </span>
      </div>

      <div className={styles.cardActions}>
        <button
          className={styles.reportBtn}
          onClick={() => onRequestReport(provider.npi)}
          disabled={isRequesting}
          aria-label={`Request report for ${provider.name}`}
        >
          {isRequesting ? "Requesting..." : "Request Report"}
        </button>
      </div>
    </div>
  );
}
