/**
 * Path B Certification page.
 *
 * Shown after login before the user can access search. Requires the user to
 * explicitly certify that they are searching for personal use only (not to
 * produce a consumer report under FCRA).
 *
 * On acceptance: sets a session cookie (medpro_path_b_certified) and redirects
 * to /search. The actual use_agreements DB row is created at payment time
 * (Phase 2-J webhook handler).
 */

"use client";

import { useRouter } from "next/navigation";
import styles from "./certify.module.css";

export default function CertifyPage() {
  const router = useRouter();

  function handleAccept() {
    // Set a simple session cookie to track certification for UX flow.
    // The legally binding agreement is recorded at payment completion
    // by the Phase 2-J webhook handler.
    document.cookie =
      "medpro_path_b_certified=1; path=/; SameSite=Strict";
    router.push("/search");
  }

  function handleDecline() {
    router.push("/");
  }

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.title}>Before You Search</h1>
        <h2 className={styles.subtitle}>Personal Use Certification Required</h2>

        <div className={styles.body}>
          <p>
            <strong>This service is for personal use only.</strong> You must certify
            that you are searching for a healthcare provider for your own personal
            use -- not on behalf of an employer, insurer, landlord, or any third party.
          </p>

          <h3>You certify that:</h3>
          <ul>
            <li>
              You are searching for a healthcare provider for your own personal
              evaluation -- not to screen, hire, tenant-screen, or otherwise make
              a decision affecting another person.
            </li>
            <li>
              You will not use the information in this report as a consumer report
              as defined under the Fair Credit Reporting Act (FCRA).
            </li>
            <li>
              You understand that this report is for informational purposes only
              and does not constitute legal, medical, or professional advice.
            </li>
            <li>
              All data is sourced from public federal records (NPPES, OIG, SAM.gov,
              CMS) which are publicly available and not personally identifiable under
              HIPAA.
            </li>
          </ul>

          <div className={styles.legalNote}>
            <strong>Path B Non-CRA Certification.</strong> By clicking "I Certify
            and Continue" you agree to our{" "}
            <a href="/terms" target="_blank" rel="noopener noreferrer">
              Terms of Service
            </a>
            . This certification is recorded at the time of any report purchase.
          </div>
        </div>

        <div className={styles.actions}>
          <button className={styles.acceptBtn} onClick={handleAccept}>
            I Certify and Continue to Search
          </button>
          <button className={styles.declineBtn} onClick={handleDecline}>
            Decline -- Go Back
          </button>
        </div>
      </div>
    </main>
  );
}
