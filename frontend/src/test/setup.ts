// Runs before every unit/component test file.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom has no layout, so scrolling does nothing (and would print an error).
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;

afterEach(() => {
  cleanup(); // remove what the test rendered
  localStorage.clear();
});
