import { getSession } from "@auth0/nextjs-auth0";
import Link from "next/link";
import UserProfile from "@/components/auth/UserProfile";
import styles from "./page.module.css";

export default async function Home() {
  const session = await getSession();
  const isAuthed = !!session;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.brand}>ResearchYourDoctor.com</span>
        <UserProfile />
      </header>

      <main className={styles.hero}>
        <h1 className={styles.heroTitle}>Know Your Provider</h1>
        <p className={styles.heroSub}>
          Federal credential verification, exclusion screening, and practice data
          -- in one comprehensive report.
        </p>
        <p className={styles.heroBadge}>Personal use only -- Path B certified</p>

        <div className={styles.actions}>
          {isAuthed ? (
            <Link href="/search" className={styles.primaryBtn}>
              Search Providers
            </Link>
          ) : (
            <a href="/api/auth/login?returnTo=/certify" className={styles.primaryBtn}>
              Sign In to Get Started
            </a>
          )}
        </div>

        <div className={styles.features}>
          <div className={styles.feature}>
            <h3>Federal Data Sources</h3>
            <p>NPPES, OIG LEIE, SAM.gov, CMS Care Compare, Medicare and Medicaid enrollment</p>
          </div>
          <div className={styles.feature}>
            <h3>Identity Verified</h3>
            <p>Multi-source identity resolution with NPI as the authoritative anchor</p>
          </div>
          <div className={styles.feature}>
            <h3>Exclusion Screening</h3>
            <p>Federal debarment and exclusion flags from OIG and SAM.gov automatically checked</p>
          </div>
        </div>
      </main>

      <footer className={styles.footer}>
        <p>
          This service is for personal use only. Reports are provided for informational purposes
          and do not constitute legal or medical advice. All data sourced from public federal
          records.
        </p>
      </footer>
    </div>
  );
}
