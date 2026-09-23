import { describe, expect, it } from "vitest";
import { backoffDelay } from "./useProjectEvents";

describe("backoffDelay", () => {
  it("doubles from 500ms and caps at 30s", () => {
    expect([0, 1, 2, 3].map(backoffDelay)).toEqual([500, 1000, 2000, 4000]);
    expect(backoffDelay(10)).toBe(30_000);
  });
});
