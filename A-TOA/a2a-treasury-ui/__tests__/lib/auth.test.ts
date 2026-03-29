import { login, logout, register } from "@/lib/auth";

describe("lib/auth", () => {
  describe("login()", () => {
    it("calls /api/auth/login with correct payload", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });
      await login("test@enterprise.com", "password123");
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/login",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            email: "test@enterprise.com",
            password: "password123",
          }),
        })
      );
    });

    it("throws error when API returns non-ok response", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid credentials" }),
      });
      await expect(login("bad@email.com", "wrong")).rejects.toEqual({
        detail: "Invalid credentials",
      });
    });

    it("returns parsed JSON on success", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });
      const result = await login("test@enterprise.com", "password123");
      expect(result).toEqual({ success: true });
    });
  });

  describe("logout()", () => {
    it("calls /api/auth/logout and redirects to /", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({ ok: true });
      delete (window as unknown as Record<string, unknown>).location;
      (window as unknown as Record<string, unknown>).location = { href: "" };
      await logout();
      expect(fetch).toHaveBeenCalledWith("/api/auth/logout", {
        method: "POST",
      });
      expect(window.location.href).toBe("/");
    });
  });

  describe("register()", () => {
    it("calls /api/auth/register with correct payload", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });
      const payload = {
        legal_name: "Test Corp",
        pan_number: "ABCDE1234F",
        gst_number: "22ABCDE1234F1Z5",
        email: "test@corp.com",
        password: "Test@1234",
        role: "buyer" as const,
      };
      await register(payload);
      expect(fetch).toHaveBeenCalledWith(
        "/api/auth/register",
        expect.objectContaining({ method: "POST" })
      );
    });

    it("throws on non-ok response", async () => {
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: false,
        json: async () => ({
          detail: "An enterprise with this email already exists.",
        }),
      });
      const payload = {
        legal_name: "Test Corp",
        pan_number: "ABCDE1234F",
        gst_number: "22ABCDE1234F1Z5",
        email: "existing@enterprise.com",
        password: "Test@1234",
        role: "buyer" as const,
      };
      await expect(register(payload)).rejects.toEqual({
        detail: "An enterprise with this email already exists.",
      });
    });
  });
});
