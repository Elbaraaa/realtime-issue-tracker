import { describe, expect, it } from "vitest";
import { errorMessage } from "./api";

describe("errorMessage", () => {
  it("uses a string detail", () => {
    expect(errorMessage({ detail: "Project not found" }, "x")).toBe("Project not found");
  });

  it("joins validation errors", () => {
    const body = { detail: [{ msg: "field required" }, { msg: "too short" }] };
    expect(errorMessage(body, "x")).toBe("field required; too short");
  });

  it("falls back for unknown shapes", () => {
    expect(errorMessage(null, "Bad Gateway")).toBe("Bad Gateway");
    expect(errorMessage({ detail: [] }, "Nope")).toBe("Nope");
  });
});
