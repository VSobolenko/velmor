import Link from "next/link";
import { DownloadButton } from "@/components/DownloadButton";
import { ShopChrome } from "@/components/ShopChrome";
import {
  CommerceApiClient,
  CommerceApiError,
  type Entitlement,
} from "@/lib/api";
import styles from "../../shop.module.css";

export const dynamic = "force-dynamic";

type Row = {
  entitlement: Entitlement;
  title: string | null;
};

type EntitlementsData =
  | { kind: "ok"; rows: Row[] }
  | { kind: "error"; message: string };

async function loadEntitlements(): Promise<EntitlementsData> {
  const client = CommerceApiClient.fromEnv();
  const entitlements = await client.listEntitlements();
  const rows: Row[] = [];
  for (const entitlement of entitlements) {
    let title: string | null = null;
    try {
      const good = await client.getGood(entitlement.candidate_id);
      title = good.title;
    } catch (error) {
      if (!(error instanceof CommerceApiError)) {
        throw error;
      }
      // Title is optional; 404 or other catalogue miss keeps id-only display.
    }
    rows.push({ entitlement, title });
  }
  return { kind: "ok", rows };
}

export default async function EntitlementsPage() {
  let data: EntitlementsData;
  try {
    data = await loadEntitlements();
  } catch (error) {
    if (error instanceof CommerceApiError) {
      data = { kind: "error", message: error.detail };
    } else if (error instanceof Error) {
      data = { kind: "error", message: error.message };
    } else {
      data = { kind: "error", message: "entitlements unavailable" };
    }
  }

  return (
    <div className={styles.page}>
      <ShopChrome tagline="Entitlements" />
      <main className={styles.main}>
        <h1 className={styles.heading}>Entitlements</h1>
        <p className={styles.status}>
          <Link href="/account">Back to account</Link>
        </p>
        {data.kind === "error" ? (
          <p className={styles.error}>{data.message}</p>
        ) : data.rows.length === 0 ? (
          <p className={styles.empty}>No entitlements yet.</p>
        ) : (
          <ul className={styles.list}>
            {data.rows.map(({ entitlement, title }) => {
              const label =
                title === null
                  ? entitlement.candidate_id
                  : `${title} (${entitlement.candidate_id})`;
              const isActive = entitlement.state === "active";
              return (
                <li
                  key={`${entitlement.order_id}:${entitlement.candidate_id}:${entitlement.granted_at}`}
                  className={styles.cartLine}
                >
                  <p>{label}</p>
                  <p className={styles.meta}>
                    {entitlement.state}
                    {entitlement.order_id !== ""
                      ? ` · order ${entitlement.order_id}`
                      : ""}
                    {` · granted ${entitlement.granted_at}`}
                  </p>
                  {isActive ? (
                    <div className={styles.actions}>
                      <DownloadButton
                        candidateId={entitlement.candidate_id}
                      />
                    </div>
                  ) : (
                    <p className={styles.empty}>
                      Revoked
                      {entitlement.revocation_reason !== undefined
                        ? `: ${entitlement.revocation_reason}`
                        : ""}
                      . No download.
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}
