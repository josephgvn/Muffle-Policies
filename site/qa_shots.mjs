// Screenshots of the built site in headless Chrome, driven over the DevTools protocol (Node 22+).
//   python3 -m http.server 8777 --directory .   (in another terminal)
//   node site/qa_shots.mjs shots.json
// shots.json: [{"url": "http://127.0.0.1:8777/", "out": "a.png", "w": 1280, "h": 800, "dpr": 2, "scheme": "dark",
//               "mobile": false, "section": ".cinema", "p": 0.4, "js": "optional async code", "wait": 700,
//               "reduce": false (prefers-reduced-motion), "nojs": false (scripts off; then section/js are skipped)}]
// "section" + "p" scroll a pinned section to that progress (0 to 1) before the picture is taken.
// The in-app browser pane is no judge of sharpness: while hidden it draws a frame only for each screenshot.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const shots = JSON.parse(readFileSync(process.argv[2], "utf8"));
const port = 9333;
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "muffle-qa-"))}`,
   "--hide-scrollbars", "--no-first-run", "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const pending = new Map(), waiters = [];
ws.addEventListener("message", (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  for (const w of waiters.filter((w) => w.method === msg.method)) { w.resolve(msg); waiters.splice(waiters.indexOf(w), 1); }
});
const send = (method, params = {}) => new Promise((resolve) => {
  const n = ++id; pending.set(n, resolve); ws.send(JSON.stringify({ id: n, method, params }));
});
const once = (method) => new Promise((resolve) => waiters.push({ method, resolve }));
const scroll = (section, p) => `const el = document.querySelector(${JSON.stringify(section)});
  scrollTo(0, el.offsetTop + ${p} * (el.offsetHeight - innerHeight));
  await new Promise((r) => setTimeout(r, 150)); dispatchEvent(new Event("resize"));
  await new Promise((r) => setTimeout(r, 1100));`;

await send("Page.enable");
for (const s of shots) {
  await send("Emulation.setDeviceMetricsOverride", { width: s.w || 1280, height: s.h || 800, deviceScaleFactor: s.dpr || 2, mobile: !!s.mobile });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: s.scheme || "light" },
                                                      { name: "prefers-reduced-motion", value: s.reduce ? "reduce" : "no-preference" }] });
  await send("Emulation.setScriptExecutionDisabled", { value: !!s.nojs });
  const loaded = once("Page.loadEventFired");
  await send("Page.navigate", { url: s.url });
  await loaded;
  await sleep(600);
  const code = (s.section ? scroll(s.section, s.p ?? 0) : "") + (s.js || "");
  if (code && !s.nojs) {
    const r = await send("Runtime.evaluate", { expression: `(async () => { ${code} })()`, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) console.log(s.out, "script error:", r.result.exceptionDetails.text);
    else if (r.result?.result?.value !== undefined) console.log(s.out, JSON.stringify(r.result.result.value));
  }
  await sleep(s.wait ?? 700);
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(s.out, Buffer.from(shot.result.data, "base64"));
}
ws.close();
chrome.kill();
