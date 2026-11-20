// UI text in Ukrainian and English. Wording follows the desktop app
// (flash/desktop/i18n.py) so both versions say the same things.
import { createContext, useContext } from "react";

export type Lang = "uk" | "en";

const uk = {
  tagline: "Тести з ваших конспектів",
  decks: "Мої тести",
  addFile: "Додати файл…",
  fromNotes: "Якщо це конспект, створити питання офлайн",
  reading: "Читаю файл…",
  emptyTitle: "Додайте перший файл",
  emptyBody: "Виберіть PDF зі збірником тестів (наприклад, «Крок») або конспект — FlasH сам створить з нього тести.",
  loading: "Завантаження…",
  start: "Почати тест",
  delete: "Видалити",
  cancel: "Скасувати",
  back: "Назад",
  confirmDelete: "Видалити «{name}»? Прогрес теж буде видалено.",
  kind_bank: "Готові тести",
  kind_generated: "Згенеровано",
  kind_ai: "Згенеровано ШІ",
  stats: "{total} питань · пройдено {seen} · вивчено {learned}",
  weak: "помилок: {n}",
  learnedPct: "{pct}% вивчено",
  setupTitle: "Налаштування тесту",
  mode: "Режим",
  mode_smart: "Розумний (спочатку слабкі й нові)",
  mode_random: "Випадковий порядок",
  mode_ordered: "По порядку",
  mode_mistakes: "Лише мої помилки",
  mode_unseen: "Лише нові питання",
  count: "Кількість питань",
  all: "Усі ({n})",
  shuffle: "Перемішувати варіанти відповідей",
  question: "Питання {i} з {n}",
  finish: "Завершити",
  next: "Далі ➜",
  results: "Результати ➜",
  correct: "Правильно!",
  wrong: "Неправильно. Правильна відповідь: {answer}",
  explanation: "Пояснення: {text}",
  keysHint: "Клавіші 1–{n} — відповідь · Enter — далі",
  grade_5: "Відмінно",
  grade_4: "Добре",
  grade_3: "Задовільно",
  grade_2: "Варто повторити",
  resultLine: "Правильних відповідей: {right} з {total}",
  chipRight: "{n} правильно",
  chipWrong: "{n} помилок",
  mistakesTitle: "Розбір помилок ({n})",
  noMistakes: "Жодної помилки. Чудово! 🎉",
  yourAnswer: "Ваша відповідь: {text}",
  rightAnswer: "Правильно: {text}",
  practiseMistakes: "Повторити мої помилки",
  home: "На головну",
  err_unreachable: "Не вдається з'єднатися з сервером FlasH. Перевірте, чи він запущений.",
  err_unsupported: "Цей тип файлу не підтримується. Використовуйте PDF, TXT або MD.",
  err_noText: "У файлі не знайдено тексту. Можливо, це скан (зображення) — такі PDF поки не підтримуються.",
  err_notBank: "Це не збірник тестів. Увімкніть створення питань з конспекту.",
  err_noQuestions: "Не вдалося створити жодного питання з цього файлу.",
  err_nothingSelected: "За цими умовами немає жодного питання.",
  err_generic: "Щось пішло не так: {message}",
};

const en: typeof uk = {
  tagline: "Tests from your study notes",
  decks: "My tests",
  addFile: "Add file…",
  fromNotes: "If it's study notes, make questions offline",
  reading: "Reading file…",
  emptyTitle: "Add your first file",
  emptyBody: "Choose a PDF with a test collection (e.g. Krok) or your study notes — FlasH will turn it into tests.",
  loading: "Loading…",
  start: "Start test",
  delete: "Delete",
  cancel: "Cancel",
  back: "Back",
  confirmDelete: "Delete “{name}”? Its progress will be deleted too.",
  kind_bank: "Test bank",
  kind_generated: "Generated",
  kind_ai: "AI-generated",
  stats: "{total} questions · {seen} attempted · {learned} learned",
  weak: "mistakes: {n}",
  learnedPct: "{pct}% learned",
  setupTitle: "Test setup",
  mode: "Mode",
  mode_smart: "Smart (weak and new first)",
  mode_random: "Random order",
  mode_ordered: "In order",
  mode_mistakes: "Only my mistakes",
  mode_unseen: "Only new questions",
  count: "Number of questions",
  all: "All ({n})",
  shuffle: "Shuffle answer options",
  question: "Question {i} of {n}",
  finish: "Finish",
  next: "Next ➜",
  results: "Results ➜",
  correct: "Correct!",
  wrong: "Wrong. Correct answer: {answer}",
  explanation: "Explanation: {text}",
  keysHint: "Keys 1–{n} answer · Enter next",
  grade_5: "Excellent",
  grade_4: "Good",
  grade_3: "Satisfactory",
  grade_2: "Needs more practice",
  resultLine: "Correct answers: {right} of {total}",
  chipRight: "{n} correct",
  chipWrong: "{n} wrong",
  mistakesTitle: "Mistakes review ({n})",
  noMistakes: "No mistakes. Excellent! 🎉",
  yourAnswer: "Your answer: {text}",
  rightAnswer: "Correct: {text}",
  practiseMistakes: "Practise my mistakes",
  home: "Home",
  err_unreachable: "Can't reach the FlasH server. Check that it is running.",
  err_unsupported: "This file type isn't supported. Use PDF, TXT or MD.",
  err_noText: "No text found in the file. It may be a scan (images) — such PDFs are not supported yet.",
  err_notBank: "This isn't a test bank. Turn on making questions from notes.",
  err_noQuestions: "Could not create any questions from this file.",
  err_nothingSelected: "No questions match these settings.",
  err_generic: "Something went wrong: {message}",
};

export const STRINGS = { uk, en };
export type Key = keyof typeof uk;
export type T = (key: Key, vars?: Record<string, string | number>) => string;

export function makeT(lang: Lang): T {
  return (key, vars) =>
    STRINGS[lang][key].replace(/\{(\w+)\}/g, (_, name: string) => String(vars?.[name] ?? `{${name}}`));
}

export function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("flash.lang");
    if (saved === "uk" || saved === "en") return saved;
  } catch {
    // storage blocked: fall back to the browser language
  }
  return navigator.language.toLowerCase().startsWith("en") ? "en" : "uk";
}

export function saveLang(lang: Lang) {
  try {
    localStorage.setItem("flash.lang", lang);
  } catch {
    // not important if it isn't remembered
  }
}

export const I18n = createContext<T>(makeT("uk"));
export const useT = () => useContext(I18n);
