import { formatINR, truncateHash, statusColor, timeAgo, cn, extractApiError } from "@/lib/utils";

describe("utils", () => {
  describe("formatINR()", () => {
    it("formats number in Indian currency format", () => {
      expect(formatINR(90270)).toContain("90,270");
    });

    it("includes ₹ symbol", () => {
      expect(formatINR(1000)).toMatch(/₹/);
    });

    it("handles zero", () => {
      expect(formatINR(0)).toContain("0");
    });

    it("handles large numbers with Indian comma grouping", () => {
      // Indian format: ₹42,50,000
      const result = formatINR(4250000);
      expect(result).toContain("42,50,000");
    });
  });

  describe("truncateHash()", () => {
    it("truncates hash to specified chars", () => {
      expect(truncateHash("a3f9b2c4d5e6f7a8b9c0d1e2f3a4b5c6", 8)).toBe("a3f9b2c4...");
    });

    it("returns empty string for empty input", () => {
      expect(truncateHash("")).toBe("");
    });

    it("uses default chars value", () => {
      const result = truncateHash("a3f9b2c4d5e6f7a8");
      expect(result).toBe("a3f9b2c4...");
    });
  });

  describe("statusColor()", () => {
    it("returns emerald for AGREED", () => {
      expect(statusColor("AGREED")).toBe("text-emerald-400");
    });

    it("returns amber for PENDING", () => {
      expect(statusColor("PENDING")).toBe("text-amber-400");
    });

    it("returns red for POLICY_BREACH", () => {
      expect(statusColor("POLICY_BREACH")).toBe("text-red-400");
    });

    it("returns gray for unknown status", () => {
      expect(statusColor("UNKNOWN_STATUS")).toBe("text-gray-400");
    });
  });

  describe("timeAgo()", () => {
    it("returns 'just now' for recent times", () => {
      const now = new Date().toISOString();
      expect(timeAgo(now)).toBe("just now");
    });

    it("returns minutes for recent past", () => {
      const fiveMinAgo = new Date(Date.now() - 5 * 60000).toISOString();
      expect(timeAgo(fiveMinAgo)).toBe("5m ago");
    });

    it("returns hours for older times", () => {
      const twoHrsAgo = new Date(Date.now() - 2 * 3600000).toISOString();
      expect(timeAgo(twoHrsAgo)).toBe("2h ago");
    });

    it("returns days for much older times", () => {
      const threeDaysAgo = new Date(Date.now() - 3 * 86400000).toISOString();
      expect(timeAgo(threeDaysAgo)).toBe("3d ago");
    });
  });

  describe("cn()", () => {
    it("joins class names", () => {
      expect(cn("foo", "bar")).toBe("foo bar");
    });

    it("filters out falsy values", () => {
      expect(cn("foo", false, null, undefined, "bar")).toBe("foo bar");
    });

    it("returns empty string for all falsy", () => {
      expect(cn(false, null, undefined)).toBe("");
    });
  });

  describe("extractApiError()", () => {
    it("returns string detail if present", () => {
      const err = { response: { data: { detail: "Bad request" } } };
      expect(extractApiError(err)).toBe("Bad request");
    });

    it("returns fallback for empty error", () => {
      expect(extractApiError({})).toBe("Something went wrong");
    });

    it("returns custom fallback", () => {
      expect(extractApiError({}, "Custom error")).toBe("Custom error");
    });

    it("handles FastAPI 422 array detail", () => {
      const err = {
        response: {
          data: {
            detail: [
              { loc: ["body", "email"], msg: "field required" },
              { loc: ["body", "password"], msg: "too short" },
            ],
          },
        },
      };
      const result = extractApiError(err);
      expect(result).toContain("email: field required");
      expect(result).toContain("password: too short");
    });
  });
});
