export type ApiError = {
  status: number;
  code: string;
  message: string;
  requestId?: string;
};

export type Principal = {
  subject: string;
  user_id: string | null;
  organization_roles: Record<string, "owner" | "admin" | "member">;
  knowledge_base_roles: Record<string, "manager" | "editor" | "viewer">;
};

export type KnowledgeBase = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description: string | null;
};

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiRequestError extends Error implements ApiError {
  status: number;
  code: string;
  requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
    credentials: "include",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiRequestError(
      response.status,
      error?.code ?? "request_failed",
      error?.message ?? "The request could not be completed.",
      error?.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
    );
  }

  return body as T;
}

export async function getPrincipal(signal?: AbortSignal): Promise<Principal> {
  return apiRequest<Principal>("/api/v1/auth/me", { signal });
}

export async function developmentLogin(
  username: string,
  password: string,
): Promise<{ subject: string }> {
  return apiRequest<{ subject: string }>("/api/v1/auth/login/development", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await apiRequest<{ logged_out: boolean }>("/api/v1/auth/logout", {
    method: "POST",
  });
}

export async function listKnowledgeBases(
  organizationId: string,
  signal?: AbortSignal,
): Promise<KnowledgeBase[]> {
  return apiRequest<KnowledgeBase[]>(
    `/api/v1/organizations/${organizationId}/knowledge-bases`,
    { signal },
  );
}

export async function getKnowledgeBase(
  organizationId: string,
  knowledgeBaseId: string,
  signal?: AbortSignal,
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(
    `/api/v1/organizations/${organizationId}/knowledge-bases/${knowledgeBaseId}`,
    { signal },
  );
}

export async function createKnowledgeBase(
  organizationId: string,
  payload: { name: string; slug: string; description?: string },
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(
    `/api/v1/organizations/${organizationId}/knowledge-bases`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function updateKnowledgeBase(
  organizationId: string,
  knowledgeBaseId: string,
  payload: { name?: string; slug?: string; description?: string | null },
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(
    `/api/v1/organizations/${organizationId}/knowledge-bases/${knowledgeBaseId}`,
    { method: "PATCH", body: JSON.stringify(payload) },
  );
}
