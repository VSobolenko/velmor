"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { CommerceApiClient } from "@/lib/api";
import { dictionaryFor } from "@/lib/i18n";
import { useLocale } from "@/lib/i18n/use-locale";

type Props = {
  candidateId: string;
};

/**
 * Issue a grant, fetch the bytes with the buyer header, trigger a browser save.
 *
 * Only an active entitlement should render this control; the grant endpoint refuses the rest,
 * and that refusal is what the failure state reports.
 */
export function DownloadButton({ candidateId }: Props) {
  const locale = useLocale();
  const dict = dictionaryFor(locale);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function onClick(): Promise<void> {
    setBusy(true);
    setFailed(false);
    const client = CommerceApiClient.fromEnv(locale);
    try {
      const grant = await client.issueGrant(candidateId);
      await client.saveDownload(grant.token, `${candidateId}.bin`);
    } catch {
      setFailed(true);
    }
    setBusy(false);
  }

  return (
    <span className="flex flex-col items-start gap-1">
      <Button
        variant="secondary"
        loading={busy}
        loadingLabel={dict["account.downloadPreparing"]}
        onClick={() => {
          void onClick();
        }}
      >
        {dict["account.download"]}
      </Button>
      {failed ? (
        <span role="alert" className="text-sm text-danger">
          {dict["account.downloadFailed"]}
        </span>
      ) : null}
    </span>
  );
}
