"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiRequestError, getPrincipal, type Principal } from "@/lib/api";

export default function Home() {
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    getPrincipal(controller.signal)
      .then(setPrincipal)
      .catch((error: unknown) => {
        if (!(error instanceof ApiRequestError) || error.status !== 401) {
          setPrincipal(null);
        }
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  if (loading) {
    return <main className="page-state" role="status">Loading workspace…</main>;
  }

  if (!principal) {
    return (
      <main className="page-state">
        <h1>Enterprise Knowledge Copilot</h1>
        <p>Your workspace for answers grounded in enterprise knowledge.</p>
        <p>Sign in to access your organization.</p>
      </main>
    );
  }

  const organizationId = Object.keys(principal.organization_roles)[0];

  return (
    <main className="content-page">
      <p className="eyebrow">Workspace</p>
      <h1>Enterprise Knowledge Copilot</h1>
      <p>Your workspace for answers grounded in enterprise knowledge.</p>
      {organizationId ? (
        <Link
          className="button"
          href={`/organizations/${organizationId}/knowledge-bases`}
        >
          Open knowledge bases
        </Link>
      ) : (
        <p>You do not belong to an organization yet.</p>
      )}
    </main>
  );
}
