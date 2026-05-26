"use client";

/**
 * ReportStatusPoller -- polls GET /api/reports/{id} every 3s until the report
 * reaches a terminal state (complete | failed).
 *
 * TanStack Query refetchInterval handles the polling loop.
 * Once status is terminal, polling stops automatically.
 */

import { useQuery } from "@tanstack/react-query";
import { getReport } from "@/lib/api";
import { ReportStatus } from "@/lib/types";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import ErrorMessage from "@/components/ui/ErrorMessage";
import PaymentGate from "./PaymentGate";
import ReportViewer from "./ReportViewer";
import styles from "./report.module.css";

const TERMINAL_STATUSES = new Set(["complete", "failed"]);
const POLL_INTERVAL_MS = 3_000;

interface ReportStatusPollerProps {
  reportId: string;
}

export default function ReportStatusPoller({ reportId }: ReportStatusPollerProps) {
  const { data, isLoading, isError, error, refetch } = useQuery<ReportStatus, Error>({
    queryKey: ["report", reportId],
    queryFn: () => getReport(reportId) as Promise<ReportStatus>,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.has(status) ? false : POLL_INTERVAL_MS;
    },
  });

  if (isLoading) {
    return <LoadingSpinner label="Loading report..." />;
  }

  if (isError) {
    return (
      <ErrorMessage
        title="Could not load report"
        message={error?.message ?? "An unexpected error occurred."}
        onRetry={() => refetch()}
      />
    );
  }

  if (!data) return null;

  // Report failed
  if (data.status === "failed") {
    return (
      <div className={styles.failed} role="alert" data-testid="report-failed">
        <h2>Report Generation Failed</h2>
        <p>{data.error_message ?? "An error occurred during report generation."}</p>
      </div>
    );
  }

  // Report is still running
  if (!TERMINAL_STATUSES.has(data.status)) {
    return (
      <div className={styles.inProgress} role="status" data-testid="report-in-progress">
        <LoadingSpinner size="lg" label="Generating report..." />
        <p className={styles.statusText}>
          Status: <strong>{data.status}</strong>
        </p>
        <p className={styles.statusHint}>
          This typically takes 10-30 seconds. This page will update automatically.
        </p>
      </div>
    );
  }

  // Report is complete but unpaid -- show payment gate
  if (data.payment_status === "unpaid" || data.payment_status === "pending") {
    return <PaymentGate reportId={reportId} npi={data.npi} />;
  }

  // Report is paid and complete -- show the HTML
  return <ReportViewer report={data} />;
}
