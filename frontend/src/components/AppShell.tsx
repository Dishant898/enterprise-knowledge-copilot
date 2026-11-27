"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiRequestError,
  getPrincipal,
  logout,
  type Principal,
} from "@/lib/api";

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const router = useRouter();
  const pathname = usePathname();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getPrincipal(controller.signal)
      .then(setPrincipal)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiRequestError && error.status === 401) {
          setSessionError("Your session has expired or is not signed in.");
        } else {
          setSessionError("Unable to verify your session. Please retry.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [pathname]);

  async function handleLogout() {
    try {
      await logout();
    } finally {
      setPrincipal(null);
      setSessionError("You have been signed out.");
      router.refresh();
    }
  }

  const organizationIds = principal
    ? Object.keys(principal.organization_roles)
    : [];

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="brand" href="/">
          Enterprise Knowledge Copilot
        </Link>
        {principal && (
          <nav aria-label="Primary navigation">
            {organizationIds.map((organizationId) => (
              <Link
                key={organizationId}
                href={`/organizations/${organizationId}/knowledge-bases`}
                aria-current={pathname.includes(organizationId) ? "page" : undefined}
              >
                Knowledge bases
              </Link>
            ))}
          </nav>
        )}
        {principal && (
          <button className="button button-secondary" type="button" onClick={handleLogout}>
            Sign out
          </button>
        )}
      </header>

      {loading ? (
        <main className="page-state" role="status" aria-live="polite">
          Loading workspace…
        </main>
      ) : sessionError && !principal ? (
        <main className="page-state">
          <h1>Sign-in required</h1>
          <p>{sessionError}</p>
          <button className="button" type="button" onClick={() => router.refresh()}>
            Retry
          </button>
        </main>
      ) : (
        children
      )}
    </div>
  );
}
