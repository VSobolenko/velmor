import { CommerceApiClient, CommerceApiError } from "@/lib/api";
import styles from "./page.module.css";

export const dynamic = "force-dynamic";

type HealthView =
  | { kind: "ok"; status: string; environment: string }
  | { kind: "error"; message: string };

async function loadHealth(): Promise<HealthView> {
  const client = CommerceApiClient.fromEnv();
  const health = await client.getHealth();
  return {
    kind: "ok",
    status: health.status,
    environment: health.environment,
  };
}

export default async function Home() {
  let view: HealthView;
  try {
    view = await loadHealth();
  } catch (error) {
    if (error instanceof CommerceApiError) {
      view = { kind: "error", message: error.detail };
    } else if (error instanceof Error) {
      view = { kind: "error", message: error.message };
    } else {
      view = { kind: "error", message: "health check failed" };
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.brand}>Proofbasket</p>
        <p className={styles.tagline}>Velmor shop</p>
      </header>
      <main className={styles.main}>
        <h1 className={styles.heading}>API status</h1>
        {view.kind === "ok" ? (
          <p className={styles.status}>
            {view.status} ({view.environment})
          </p>
        ) : (
          <p className={styles.error}>{view.message}</p>
        )}
      </main>
    </div>
  );
}
