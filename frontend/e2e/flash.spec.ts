// What a student does, in a real browser, against the real containers.
// Each test uploads its own deck with a unique name and deletes it at the end,
// so the tests can run against a server that already has data.
import { expect, test, type Page } from "@playwright/test";

// The right answer is first in every question (as in Krok booklets).
const BANK = `1. Which organ pumps blood?
Heart
Liver
Lungs
Kidneys

2. Which gas do plants absorb?
Carbon dioxide
Oxygen
Nitrogen
Helium

3. What is the chemical symbol of sodium?
Na
K
Ca
S
`;

// Fail any test that logs a browser error, including content blocked by the security headers (CSP).
// 4xx responses the test causes on purpose are expected, so they don't count.
let problems: string[] = [];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().includes("status of 415")) problems.push(msg.text());
  });
  page.on("pageerror", (err) => problems.push(err.message));
  await page.addInitScript(() => {
    if (!localStorage.getItem("flash.lang")) localStorage.setItem("flash.lang", "en");
  });
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

function uniqueName() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

async function uploadBank(page: Page, name: string) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "My tests" })).toBeVisible();
  await page.locator("#file").setInputFiles({ name: `${name}.txt`, mimeType: "text/plain", buffer: Buffer.from(BANK) });
  const card = page.locator("article", { has: page.getByRole("heading", { name }) });
  await expect(card).toBeVisible();
  await expect(card).toContainText("3 questions");
  return card;
}

async function deleteDeck(page: Page, name: string) {
  await page.getByRole("button", { name: /FlasH/ }).click();
  const card = page.locator("article", { has: page.getByRole("heading", { name }) });
  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Delete" }).click(); // confirm
  await expect(card).toHaveCount(0);
}

async function startOrderedUnshuffled(page: Page, card: ReturnType<Page["locator"]>) {
  await card.getByRole("button", { name: /Start test/ }).click();
  await expect(page.getByText("Test setup")).toBeVisible();
  await page.getByLabel("In order").check();
  await page.getByLabel("Shuffle answer options").uncheck();
  await page.getByRole("button", { name: /Start test/ }).click();
  await expect(page.getByText("Question 1 of 3")).toBeVisible();
}

test("upload a test collection, take a test, practise the mistakes", async ({ page }) => {
  const name = uniqueName();
  const card = await uploadBank(page, name);
  await startOrderedUnshuffled(page, card);

  // Option 1 is right (unshuffled); answer right, wrong, right.
  for (const [choice, verdict] of [
    ["Heart", "Correct!"],
    ["Oxygen", "Wrong. Correct answer: Carbon dioxide"],
    ["Na", "Correct!"],
  ]) {
    await page.getByRole("button", { name: choice, exact: false }).first().click();
    await expect(page.getByRole("status")).toContainText(verdict);
    await page.getByRole("button", { name: /Next|Results/ }).click();
  }

  await expect(page.getByText("Correct answers: 2 of 3")).toBeVisible();
  await expect(page.getByRole("img", { name: "67%" })).toBeVisible();
  await expect(page.locator(".mistakes li")).toHaveCount(1);
  await expect(page.locator(".mistakes li")).toContainText("Which gas do plants absorb?");

  await page.getByRole("button", { name: "Practise my mistakes" }).click();
  await expect(page.getByText("Question 1 of 1")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Which gas do plants absorb?" })).toBeVisible();

  await page.getByRole("button", { name: /Finish/ }).click();
  await expect(page.getByRole("heading", { name: "My tests" })).toBeVisible();
  await expect(card).toContainText("3 attempted");
  await deleteDeck(page, name);
});

test("answer with the keyboard", async ({ page, isMobile }) => {
  test.skip(isMobile, "phones have no keyboard shortcuts");
  const name = uniqueName();
  const card = await uploadBank(page, name);
  await startOrderedUnshuffled(page, card);

  for (let i = 1; i <= 3; i++) {
    await page.keyboard.press("1");
    await expect(page.getByRole("status")).toContainText("Correct!");
    await page.keyboard.press("Enter");
  }
  await expect(page.getByText("Correct answers: 3 of 3")).toBeVisible();
  await expect(page.getByText("No mistakes. Excellent!")).toBeVisible();
  await deleteDeck(page, name);
});

test("the language choice is remembered", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "UA" }).click();
  await expect(page.getByRole("heading", { name: "Мої тести" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Мої тести" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "uk");
  await page.getByRole("button", { name: "EN" }).click();
});

test("an unsupported file is explained", async ({ page }) => {
  await page.goto("/");
  await page.locator("#file").setInputFiles({ name: "slides.txt.exe", mimeType: "application/octet-stream", buffer: Buffer.from("x") });
  await expect(page.getByRole("alert")).toContainText("This file type isn't supported");
});

test("the page fits the screen and can be installed", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "My tests" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);

  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest.icons.map((i: { src: string }) => i.src)).toContain("/icon-512.png");
  expect((await request.get("/icon-180.png")).headers()["content-type"]).toBe("image/png");
  expect((await request.get("/api/health")).ok()).toBeTruthy();
});
