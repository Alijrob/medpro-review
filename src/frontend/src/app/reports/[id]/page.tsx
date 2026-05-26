/**
 * Report detail page -- /reports/{id}
 *
 * Shows report status with live polling (ReportStatusPoller).
 * Once complete: shows PaymentGate (if unpaid) or ReportViewer (if paid).
 */

import ReportStatusPoller from "@/components/report/ReportStatusPoller";
import UserProfile from "@/components/auth/UserProfile";
import styles from "./report.module.css";

interface ReportPageProps {
  params: { id: string };
}

export default function ReportPage({ params }: ReportPageProps) {
  const { id } = params;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <a href="/search" className={styles.backLink}>
            Back to Search
          </a>
          <span className={styles.brand}>Report</span>
        </div>
        <UserProfile />
      </header>

      <main className={styles.main}>
        <ReportStatusPoller reportId={id} />
      </main>

      <footer className={styles.footer}>
        <p>
          Report data sourced from public federal records. For personal use only.
          Not legal or medical advice.
        </p>
      </footer>
    </div>
  );
}
