"use client";

import styles from "./auth.module.css";

export default function LogoutButton() {
  return (
    <a href="/api/auth/logout" className={styles.logoutBtn}>
      Sign Out
    </a>
  );
}
