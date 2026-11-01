/* Owns a temporary scripted workspace. Never points Reset at the user's data. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const {
  chromium,
  expect,
} = require("../frontend/node_modules/@playwright/test");

const root = path.resolve(__dirname, "..");
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "swarm-browser-"));
const evidence = path.join(root, "artifacts", "frontend-browser-check");
fs.mkdirSync(evidence, { recursive: true });
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let server, browser;

async function main() {
  const listener = net.createServer();
  await new Promise((resolve) => listener.listen(0, "127.0.0.1", resolve));
  const port = listener.address().port;
  await new Promise((resolve) => listener.close(resolve));
  const url = `http://127.0.0.1:${port}`;
  server = spawn(
    path.join(root, ".venv/bin/python"),
    [
      "-u",
      "-m",
      "swarm.demo",
      "--scripted",
      "--port",
      String(port),
      "--output",
      temporary,
    ],
    { cwd: root, stdio: "ignore" },
  );
  for (let i = 0; i < 300; i++) {
    try {
      if ((await fetch(url + "/api/config")).ok) break;
    } catch {}
    if (server.exitCode !== null) throw new Error("Test launcher exited");
    await pause(100);
  }
  const config = await (await fetch(url + "/api/config")).json();
  assert.equal(config.model, "scripted-fixture");
  browser = await chromium.launch({
    executablePath:
      process.env.SWARM_CHROME ||
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const state = async () => (await fetch(url + "/api/state")).json();
  const waitIdle = async () =>
    expect
      .poll(async () => (await state()).busy, { timeout: 180000 })
      .toBe(false);
  const start = page.getByRole("button", { name: "Start run", exact: true });
  await page.goto(url + "/dashboard", { waitUntil: "domcontentloaded" });
  await expect(start).toBeEnabled();
  await page.getByRole("button", { name: "Get started", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  assert(
    await page
      .getByRole("dialog")
      .evaluate((el) => el.contains(document.activeElement)),
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  // Removed presentation sections and metadata stay absent on both pages.
  for (const selector of [
    "#workflow",
    "#oversight",
    "#value",
    '[aria-label="Filter planted bugs"]',
  ]) {
    await expect(page.locator(selector)).toHaveCount(0);
  }
  await page.evaluate(() => window.scrollTo(0, 500));
  await expect
    .poll(() =>
      page
        .locator("header")
        .evaluate((el) => el.getBoundingClientRect().bottom),
    )
    .toBeLessThanOrEqual(0);
  await page.evaluate(() => window.scrollTo(0, 200));
  await expect
    .poll(() =>
      page.locator("header").evaluate((el) => el.getBoundingClientRect().top),
    )
    .toBe(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await start.click();
  await expect(
    page.getByRole("button", { name: "Stop", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await waitIdle();
  // Finish a full run, then inspect and download its actual artifacts.
  await expect(start).toBeEnabled();
  await start.click();
  await waitIdle();
  assert.equal((await state()).error, null);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("link", { name: "Download JSON", exact: true })).toBeVisible({timeout: 20000});
  await expect(page.getByText(/distinct bugs verified/)).toHaveCount(0);
  await expect(page.locator('a[href$=".pdf"]')).toHaveCount(0);
  await page
    .getByRole("button", { name: "Inspect recorded actions", exact: true })
    .click();
  await expect(
    page.getByRole("table", { name: "Latest twenty recorded actions" }),
  ).toBeVisible();
  const report = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download JSON", exact: true }).click();
  const reportFile = path.join(temporary, "download.json");
  await (await report).saveAs(reportFile);
  assert(JSON.parse(fs.readFileSync(reportFile, "utf8")).findings.length >= 8);
  // Both conditions and six matched comparison runs use the same controls.
  await page
    .getByRole("button", { name: "Run benchmark", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("six-run benchmark");
  await page
    .getByRole("button", { name: "Start benchmark", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Stop", exact: true }),
  ).toBeEnabled();
  await waitIdle();
  const measured = await state();
  assert.equal(measured.error, null);
  assert.equal(measured.benchmark.runs.length, 6);
  assert.equal(measured.gate.source, "scripted-fixture");
  assert.equal(measured.gate.complete, false);
  await page.getByRole("button", { name: "Condition B", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: /Condition B/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Condition C", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Phase 2 · planned", exact: true }),
  ).toHaveCount(0);
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.screenshot({
      path: path.join(evidence, `dashboard-${width}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  // Reset cancellation preserves history; confirmation clears only our owned workspace.
  await page
    .getByRole("button", { name: "Reset workspace", exact: true })
    .click();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  assert((await (await fetch(url + "/api/history")).json()).length > 0);
  await page
    .getByRole("button", { name: "Reset workspace", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Reset workspace", exact: true })
    .click();
  await waitIdle();
  await expect(
    page.getByText("Recorded round activity will appear here.", {
      exact: true,
    }),
  ).toBeVisible();
  assert.deepEqual(await (await fetch(url + "/api/history")).json(), []);
  await expect(
    page.getByRole("link", { name: "Open Bazaar ↗", exact: true }),
  ).toHaveCount(0);
  await page.goto(url + "/bazaar/", { waitUntil: "domcontentloaded" });
  await expect(page).toHaveURL(/\/bazaar\/$/);
  await expect(page).toHaveTitle(/Bazaar/);
  await expect(
    page.getByRole("link", { name: "bazaar✳", exact: true }).first(),
  ).toBeVisible();
  assert.deepEqual(errors, []);
  fs.writeFileSync(
    path.join(evidence, "result.json"),
    JSON.stringify(
      {
        passed: true,
        source: "scripted-fixture",
        browserErrors: errors,
        widths: [390, 768, 1440],
        workflows: [
          "start/stop",
          "history/download",
          "six-run benchmark",
          "confirmed reset",
          "scroll navigation and section removal",
          "Bazaar route",
        ],
      },
      null,
      2,
    ),
  );
  console.log(
    "PASS browser workflows, responsive layouts and modal keyboard controls; scripted only, no paid AI.",
  );
}

main()
  .catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  })
  .finally(async () => {
    await browser?.close();
    if (server && server.exitCode === null) {
      server.kill("SIGINT");
      await pause(1000);
      if (server.exitCode === null) server.kill("SIGINT");
      await Promise.race([
        new Promise((resolve) => server.once("exit", resolve)),
        pause(10000),
      ]);
    }
    fs.rmSync(temporary, { recursive: true, force: true });
  });
