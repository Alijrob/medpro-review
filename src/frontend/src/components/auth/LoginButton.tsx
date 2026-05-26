"use client";

import styles from "./auth.module.css";

interface LoginButtonProps {
  returnTo?: string;
}

export default function LoginButton({ returnTo = "/" }: LoginButtonProps) {
  return (
    <a
      href={`/api/auth/login?returnTo=${encodeURIComponent(returnTo)}`}
      className={styles.loginBtn}
    >
      Sign In
    </a>
  );
}
