"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  ApiRequestError,
  getKnowledgeBase,
  getPrincipal,
  updateKnowledgeBase,
  type KnowledgeBase,
  type Principal,
} from "@/lib/api";

export default function KnowledgeBaseDetailPage() {
  const { organizationId, knowledgeBaseId } = useParams<{
    organizationId: string;
    knowledgeBaseId: string;
  }>();
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<ApiRequestError | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    try {
      const [identity, item] = await Promise.all([
        getPrincipal(controller.signal),
        getKnowledgeBase(organizationId, knowledgeBaseId, controller.signal),
      ]);
      setPrincipal(identity);
      setKnowledgeBase(item);
    } catch (requestError) {
      if (requestError instanceof ApiRequestError) setError(requestError);
      else setError(new ApiRequestError(0, "network_error", "Could not load the knowledge base."));
    } finally {
      setLoading(false);
    }
  }, [organizationId, knowledgeBaseId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timeout);
  }, [load]);

  const organizationRole = principal?.organization_roles[organizationId];  const knowledgeBaseRole = principal?.knowledge_base_roles[
    `${organizationId}:${knowledgeBaseId}`
  ];
  const canEdit =
    organizationRole === "owner" ||
    organizationRole === "admin" ||
    knowledgeBaseRole === "manager";

  async function handleUpdate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canEdit) return;
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setSavedMessage(null);
    setError(null);
    try {
      const updated = await updateKnowledgeBase(organizationId, knowledgeBaseId, {
        name: String(form.get("name") ?? "").trim(),
        slug: String(form.get("slug") ?? "").trim(),
        description: String(form.get("description") ?? "").trim() || null,
      });
      setKnowledgeBase(updated);
      setSavedMessage("Changes saved.");
    } catch (requestError) {
      if (requestError instanceof ApiRequestError) setError(requestError);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <main className="page-state" role="status">Loading knowledge base…</main>;
  }

  if (error) {
    return (
      <main className="page-state" role="alert">
        <h1>{error.status === 403 || error.status === 404 ? "Not authorized" : "Knowledge base unavailable"}</h1>
        <p>{error.status === 403 || error.status === 404 ? "This knowledge base is not available to you." : error.message}</p>
        {error.requestId && <small>Request ID: {error.requestId}</small>}
        {error.status !== 403 && error.status !== 404 && (
          <button className="button" type="button" onClick={() => void load()}>
            Retry
          </button>
        )}
      </main>
    );
  }

  if (!knowledgeBase) return null;

  return (
    <main className="content-page">
      <Link
        className="back-link"
        href={`/organizations/${organizationId}/knowledge-bases`}
      >
        ← Knowledge bases
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Knowledge base</p>
          <h1>{knowledgeBase.name}</h1>
        </div>
      </div>

      {savedMessage && <p className="success-message" role="status">{savedMessage}</p>}

      {canEdit ? (
        <form className="card form" onSubmit={handleUpdate}>
          <h2>Edit knowledge base</h2>
          <label htmlFor="kb-name">Name</label>
          <input id="kb-name" name="name" defaultValue={knowledgeBase.name} required maxLength={200} />
          <label htmlFor="kb-slug">Slug</label>
          <input
            id="kb-slug"
            name="slug"
            defaultValue={knowledgeBase.slug}
            required
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            maxLength={100}
          />
          <label htmlFor="kb-description">Description</label>
          <textarea
            id="kb-description"
            name="description"
            defaultValue={knowledgeBase.description ?? ""}
            maxLength={1000}
          />
          <button className="button" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </form>
      ) : (
        <section className="card">
          <h2>{knowledgeBase.slug}</h2>
          <p>{knowledgeBase.description || "No description."}</p>
        </section>
      )}
    </main>
  );
}
