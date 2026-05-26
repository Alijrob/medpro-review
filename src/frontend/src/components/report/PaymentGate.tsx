"use client";

/**
 * PaymentGate -- shown when report is complete but payment_status === "unpaid".
 *
 * Calls POST /api/payments/checkout with certified_personal_use_only=true
 * (user must have passed Path B certification to reach this page).
 * On success, redirects the browser to Stripe Checkout URL.
 */

import { useState } from "react";
import { createCheckout, ApiError } from "@/lib/api";
import styles from "./report.module.css";

interface PaymentGateProps {
  reportId: string;
  npi: string;
  priceUsd?: number;
}

export default function PaymentGate({ reportId, npi, priceUsd = 15 }: PaymentGateProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePayment() {
    setLoading(true);
    setError(null);
    try {
      const result = await createCheckout({
        report_id: reportId,
        npi,
        certified_personal_use_only: true,
      });
      // Redirect to Stripe Checkout (or mock URL in dev)
      window.location.href = result.checkout_url;
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Payment setup failed. Please try again.";
      setError(msg);
      setLoading(false);
    }
  }

  return (
    <div className={styles.paymentGate} data-testid="payment-gate">
      <div className={styles.paymentIcon} aria-hidden="true">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
          <line x1="1" y1="10" x2="23" y2="10" />
        </svg>
      </div>
      <h2 className={styles.paymentTitle}>Unlock This Report</h2>
      <p className={styles.paymentDesc}>
        This report is ready. Purchase access to view the complete provider intelligence
        report including credential verification, federal exclusion status, and more.
      </p>
      <p className={styles.paymentPrice}>${priceUsd.toFixed(2)} one-time</p>
      <p className={styles.paymentDisclaimer}>
        Personal use only. By proceeding you confirm this report is for your own personal
        use in evaluating a healthcare provider (Path B certification).
      </p>
      {error && (
        <p className={styles.paymentError} role="alert">
          {error}
        </p>
      )}
      <button
        className={styles.payBtn}
        onClick={handlePayment}
        disabled={loading}
        aria-label="Pay and unlock report"
      >
        {loading ? "Redirecting to Checkout..." : `Pay $${priceUsd.toFixed(2)} - View Report`}
      </button>
    </div>
  );
}
