import { afterEach, describe, expect, it, vi } from "vitest";
import { STRINGS, initialLang, makeT, saveLang } from "./i18n";

describe("makeT", () => {
  it("fills in placeholders", () => {
    expect(makeT("en")("question", { i: 2, n: 30 })).toBe("Question 2 of 30");
    expect(makeT("uk")("question", { i: 2, n: 30 })).toBe("Питання 2 з 30");
  });

  it("keeps a placeholder that has no value, so the gap is visible", () => {
    expect(makeT("en")("question", { i: 2 })).toBe("Question 2 of {n}");
  });
});

describe("translations", () => {
  it("use the same placeholders in both languages", () => {
    const names = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(STRINGS.uk) as (keyof typeof STRINGS.uk)[]) {
      expect(names(STRINGS.en[key]), key).toEqual(names(STRINGS.uk[key]));
    }
  });
});

describe("language choice", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("remembers the chosen language", () => {
    saveLang("en");
    expect(initialLang()).toBe("en");
    saveLang("uk");
    expect(initialLang()).toBe("uk");
  });

  it("falls back to the browser language", () => {
    vi.stubGlobal("navigator", { language: "en-GB" });
    expect(initialLang()).toBe("en");
    vi.stubGlobal("navigator", { language: "uk-UA" });
    expect(initialLang()).toBe("uk");
  });

  it("works when storage is blocked (private mode)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.stubGlobal("navigator", { language: "en-US" });
    expect(() => saveLang("uk")).not.toThrow();
    expect(initialLang()).toBe("en");
  });
});
