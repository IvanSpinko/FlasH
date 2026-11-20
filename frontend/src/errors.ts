import { ApiError } from "./api";
import type { T } from "./i18n";

/** A message for the student, in their language, for an error from the API. */
export function errorText(t: T, err: unknown, action: "upload" | "start" | "other"): string {
  if (!(err instanceof ApiError)) return t("err_generic", { message: String(err) });
  if (err.status === 0) return t("err_unreachable");
  if (action === "upload") {
    if (err.status === 415) return t("err_unsupported");
    if (err.message.startsWith("No text")) return t("err_noText");
    if (err.message.startsWith("Not a test bank")) return t("err_notBank");
    if (err.message.startsWith("No questions")) return t("err_noQuestions");
  }
  if (action === "start" && err.status === 422) return t("err_nothingSelected");
  return t("err_generic", { message: err.message });
}
