"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ApiRequestError,
  createKnowledgeBase,
  getPrincipal,
  listKnowledgeBases,
  type KnowledgeBase,
  type Principal,
} from "@/lib/api";

export default function KnowledgeBasesPage() {
  const { organizationId } = useParams<{ organizationId: string }>();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    try {
      const [identity, items] = await Promise.all([
        getPrincipal(controller.signal),
        listKnowledgeBases(organizationId, controller.signal),
      ]);
      setPrincipal(identity);
      setKnowledgeBases(items);
    } catch (requestError) {
      if (requestError instanceof ApiRequestError) setError(requestError);
      else setError(new ApiRequestError(0, "network_error", "Could not load knowledge bases."));
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  const canCreate =
    principal?.organization_roles[organizationId] === "owner" ||
    principal?.organization_roles[organizationId] === "admin";

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) return;
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setSavedMessage(null);
    setError(null);
    try {
      const created = await createKnowledgeBase(organizationId, {
        name: String(form.get("name") ?? "").trim(),
        slug: String(form.get("slug") ?? "").trim(),
        description: String(form.get("description") ?? "").trim(),
      });
      setKnowledgeBases((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
      setSavedMessage(`${created.name} was created.`);
      setShowCreate(false);
    } catch (requestError) {
      if (requestError instanceof ApiRequestError) setError(requestError);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="page-state" role="status">Loading knowledge bases…</main>;
  }

  if (error) {
    return (
      <main className="page-state" role="alert">
        <h1>Knowledge bases unavailable</h1>
        <p>{error.message}</p>
        {error.requestId && <small>Request ID: {error.requestId}</small>}
        <button className="button" type="button" onClick={() => void load()}>
          Retry
        </button>
      </main>
    );
  }

  if (!principal?.organization_roles[organizationId]) {
    return (
      <main className="page-state">
        <h1>Not authorized</h1>
        <p>You do not have access to this organization.</p>
      </main>
    );
  }

  return (
    <main className="content-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Knowledge</p>
          <h1>Knowledge bases</h1>
        </div>
        {canCreate && (
          <button className="button" type="button" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Cancel" : "Create knowledge base"}
          </button>
        )}
      </div>

      {savedMessage && <p className="success-message" role="status">{savedMessage}</p>}

      {showCreate && (
        <form className="card form" onSubmit={handleCreate}>
          <h2>Create knowledge base</h2>
          <label htmlFor="kb-name">Name</label>
          <input id="kb-name" name="name" required maxLength={200} />
          <label htmlFor="kb-slug">Slug</label>
          <input id="kb-slug" name="slug" required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" maxLength={100} />
          <label htmlFor="kb-description">Description</label>
          <textarea id="kb-description" name="description" maxLength={1000} />
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Create"}
          </button>
        </form>
      )}

      {knowledgeBases.length === 0 ? (
        <section className="card empty-state">
          <h2>No knowledge bases yet</h2>
          <p>Authorized knowledge bases will appear here.</p>
        </section>
      ) : (
        <ul className="knowledge-base-list">
          {knowledgeBases.map((knowledgeBase) => (
            <li className="card" key={knowledgeBase.id}>
              <Link href={`/organizations/${organizationId}/knowledge-bases/${knowledgeBase.id}`}>
                <h2>{knowledgeBase.name}</h2>
              </Link>
              <p>{knowledgeBase.description || "No description."}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
