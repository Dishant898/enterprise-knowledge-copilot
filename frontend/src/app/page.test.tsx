import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

describe("home page", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders the signed-out heading", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "unauthorized", message: "Authentication required." } }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<Home />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Enterprise Knowledge Copilot" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Sign in to access your organization.")).toBeInTheDocument();
  });

  it("offers the first authorized organization", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify({
        subject: "dev|owner",
        user_id: "user-1",
        organization_roles: { "org-1": "owner" },
        knowledge_base_roles: {},
      }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    render(<Home />);

    expect(await screen.findByRole("link", { name: "Open knowledge bases" })).toHaveAttribute(
      "href",
      "/organizations/org-1/knowledge-bases",
    );
  });
});
