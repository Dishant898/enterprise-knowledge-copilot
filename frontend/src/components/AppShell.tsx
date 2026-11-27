"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiRequestError,
  developmentLogin,
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

  async function handleDevelopmentLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setSessionError(null);
    setLoading(true);
    try {
      await developmentLogin(
        String(form.get("username") ?? ""),
        String(form.get("password") ?? ""),
      );
      const principal = await getPrincipal();
      setPrincipal(principal);
    } catch (error) {
      if (error instanceof ApiRequestError) {
        setSessionError(error.message);
      } else {
        setSessionError("Unable to start the local sign-in.");
      }
    } finally {
      setLoading(false);
    }
  }

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
          <form className="login-form" onSubmit={handleDevelopmentLogin}>
            <label htmlFor="login-username">Username</label>
            <input id="login-username" name="username" autoComplete="username" required />
            <label htmlFor="login-password">Password</label>
            <input id="login-password" name="password" type="password" autoComplete="current-password" required />
            <button className="button" type="submit">
              Sign in
            </button>
          </form>
        </main>
      ) : (
        children
      )}
    </div>
  );
}
