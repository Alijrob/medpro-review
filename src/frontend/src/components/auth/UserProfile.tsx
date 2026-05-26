"use client";

import { useUser } from "@auth0/nextjs-auth0/client";
import LoginButton from "./LoginButton";
import LogoutButton from "./LogoutButton";
import styles from "./auth.module.css";

export default function UserProfile() {
  const { user, isLoading } = useUser();

  if (isLoading) return <span className={styles.loading}>...</span>;

  if (!user) return <LoginButton />;

  return (
    <div className={styles.profile}>
      <span className={styles.email}>{user.email ?? user.name ?? "User"}</span>
      <LogoutButton />
    </div>
  );
}
