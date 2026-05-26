"use client";

import { FormEvent, useState } from "react";
import styles from "./search.module.css";

export interface SearchBarProps {
  onSearch: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export default function SearchBar({
  onSearch,
  isLoading = false,
  placeholder = "Search by name or 10-digit NPI...",
}: SearchBarProps) {
  const [value, setValue] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      onSearch(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className={styles.searchForm} role="search">
      <input
        type="search"
        className={styles.searchInput}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        aria-label="Search providers"
        disabled={isLoading}
      />
      <button
        type="submit"
        className={styles.searchBtn}
        disabled={isLoading || value.trim().length === 0}
        aria-label="Submit search"
      >
        {isLoading ? "Searching..." : "Search"}
      </button>
    </form>
  );
}
