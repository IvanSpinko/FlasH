import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { errorText } from "./errors";
import { makeT } from "./i18n";

const t = makeT("en");

describe("errorText", () => {
  it.each([
    [0, "unreachable", "upload", "Can't reach the FlasH server"],
    [413, "Too Large", "upload", "too large"],
    [415, "Unsupported file type", "upload", "isn't supported"],
    [422, "Could not read the file; it may be damaged", "upload", "Could not read the file"],
    [422, "No text found (a scanned PDF ...)", "upload", "No text found"],
    [422, "Not a test bank; use generate=offline", "upload", "isn't a test bank"],
    [422, "No questions could be found or generated", "upload", "Could not create any questions"],
    [422, "No questions match this selection", "start", "No questions match"],
  ] as const)("status %i (%s) during %s", (status, message, action, expected) => {
    expect(errorText(t, new ApiError(status, message), action)).toContain(expected);
  });

  it("shows the API's own message for anything else", () => {
    expect(errorText(t, new ApiError(500, "boom"), "other")).toBe("Something went wrong: boom");
  });

  it("handles errors that aren't from the API", () => {
    expect(errorText(t, new Error("bug"), "other")).toBe("Something went wrong: Error: bug");
  });
});
