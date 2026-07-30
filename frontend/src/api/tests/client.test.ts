import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "@/api/client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiRequest", () => {
  it("sends JSON headers and bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/api/v1/me/", {
      token: "abc123",
      method: "PATCH",
      body: { display_name: "Lecteur" }
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/me/",
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          Authorization: "Bearer abc123",
          "Content-Type": "application/json",
          Accept: "application/json"
        }),
        body: JSON.stringify({ display_name: "Lecteur" })
      })
    );
  });

  it("raises ApiError from normalized error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "entitlement_required",
              message: "An active read entitlement is required.",
              field_errors: {}
            }
          }),
          { status: 403, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(apiRequest("/api/v1/reader/sessions/", { method: "POST" }))
      .rejects.toMatchObject({
        code: "entitlement_required",
        status: 403
      });
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    await expect(apiRequest("/api/v1/auth/logout/", { method: "POST" })).resolves.toBeUndefined();
  });
});
