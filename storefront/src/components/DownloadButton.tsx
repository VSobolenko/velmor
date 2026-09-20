"use client";

import { useState } from "react";
import {
  CommerceApiClient,
  CommerceApiError,
} from "@/lib/api";
import styles from "@/app/shop.module.css";

type Props = {
  candidateId: string;
  label?: string;
};

/** Issue a grant, fetch bytes with X-Buyer-Id, trigger a browser save. */
export function DownloadButton({ candidateId, label = "Download" }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    const client = CommerceApiClient.fromEnv();
    try {
      const grant = await client.issueGrant(candidateId);
      await client.saveDownload(grant.token, `${candidateId}.bin`);
    } catch (err) {
      if (err instanceof CommerceApiError) {
        setError(err.detail);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("download failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className={styles.downloadControl}>
      <button
        type="button"
        className={styles.button}
        onClick={onClick}
        disabled={busy}
      >
        {busy ? "Preparing…" : label}
      </button>
      {error !== null ? <p className={styles.error}>{error}</p> : null}
    </span>
  );
}
