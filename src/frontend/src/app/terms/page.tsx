/**
 * /terms -- Terms of Service placeholder.
 *
 * Legal copy is pending attorney review.  This page satisfies the
 * link in the footer and certify flow until the full ToS is drafted.
 */

import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service | Research Your Doctor",
  description: "Terms of Service for researchyourdoctor.com",
};

export default function TermsPage() {
  return (
    <main
      style={{
        maxWidth: "720px",
        margin: "0 auto",
        padding: "3rem 1.5rem",
        fontFamily: "system-ui, sans-serif",
        lineHeight: 1.7,
        color: "#1a1a2e",
      }}
    >
      <h1 style={{ fontSize: "2rem", fontWeight: 700, marginBottom: "0.5rem" }}>
        Terms of Service
      </h1>
      <p style={{ color: "#666", marginBottom: "2rem", fontSize: "0.9rem" }}>
        Last updated: coming soon
      </p>

      <div
        style={{
          background: "#fff8e1",
          border: "1px solid #ffd54f",
          borderRadius: "8px",
          padding: "1.25rem 1.5rem",
          marginBottom: "2rem",
        }}
      >
        <strong>These Terms of Service are currently being drafted</strong> with
        legal counsel. They will be published here before researchyourdoctor.com
        opens to the public.
      </div>

      <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem" }}>
        Personal Use Only (Path B)
      </h2>
      <p>
        This service provides public-record information for personal research use only.
        Reports from researchyourdoctor.com may <strong>not</strong> be used for
        employment screening, tenant screening, credit decisions, insurance underwriting,
        or any other purpose regulated by the Fair Credit Reporting Act (FCRA).
      </p>

      <h2
        style={{
          fontSize: "1.25rem",
          fontWeight: 600,
          marginBottom: "0.75rem",
          marginTop: "2rem",
        }}
      >
        Accuracy Disclaimer
      </h2>
      <p>
        Reports are compiled from publicly available sources and are provided
        "as is" without warranty. Information may be incomplete, out of date,
        or contain errors. Always verify important information directly with
        the relevant licensing authority.
      </p>

      <h2
        style={{
          fontSize: "1.25rem",
          fontWeight: 600,
          marginBottom: "0.75rem",
          marginTop: "2rem",
        }}
      >
        Questions
      </h2>
      <p>
        For questions about these terms, contact us at{" "}
        <a
          href="mailto:legal@pagiosystems.com"
          style={{ color: "#4361ee", textDecoration: "underline" }}
        >
          legal@pagiosystems.com
        </a>
        .
      </p>
    </main>
  );
}
