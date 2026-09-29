/* Muffle website motion. The page reads fine without any of it: with no script, or with reduced motion,
   everything shows in its final state (the opening as a still picture). */
(() => {
  const d = document;
  const root = d.documentElement;
  const motion = root.classList.contains("motion");
  const observe = "IntersectionObserver" in window;
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const rtl = root.dir === "rtl";
  /** 0 when a pinned section's top reaches the top of the window, 1 when its end does. */
  const progress = (el, pinHeight) => {
    const r = el.getBoundingClientRect();
    const run = r.height - pinHeight;
    return run > 0 ? clamp(-r.top / run) : (r.top < 0 ? 1 : 0);
  };

  const nav = d.querySelector(".nav");
  const updateNav = () => nav && nav.classList.toggle("scrolled", scrollY > 8);

  // Reveal on scroll, with a safety net for browsers that never report visibility.
  const reveals = d.querySelectorAll(".reveal");
  const showAll = () => reveals.forEach((el) => el.classList.add("in"));
  if (!motion || !observe) {
    showAll();
  } else {
    const seen = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      seen.unobserve(entry.target);
    }), { rootMargin: "0px 0px -6% 0px", threshold: 0.1 });
    reveals.forEach((el) => seen.observe(el));
    setTimeout(() => { if (!d.querySelector(".reveal.in")) showAll(); }, 2500);
    addEventListener("beforeprint", showAll);
  }

  const parts = [];

  // ---------- Opening: the real panel, drawn on a canvas ----------
  // The panel rises, the page zooms into the mute button, which dips as it turns red, zooms back out, then
  // points at the microphones, the level and the quick switches in turn. Every frame is drawn straight from the
  // app's own renders (2x, with 8x and 4x close-ups) at the screen's own resolution, so no zoom is ever soft:
  // a scaled page layer would be left to the browser, which may draw it from a low-resolution copy.
  const cinema = d.querySelector(".cinema");
  if (cinema && motion) {
    const pin = cinema.querySelector(".cinema-pin");
    const scene = cinema.querySelector(".scene");
    const canvas = scene.querySelector("canvas");
    const ctx = canvas.getContext("2d");
    const caps = [...cinema.querySelectorAll(".cap")];
    const L = JSON.parse(scene.dataset.layout || "{}");
    // Captions: headline, one press, every control, microphones, level, switches.
    const RANGES = [[0, 0, 0.03, 0.09], [0.09, 0.14, 0.44, 0.49], [0.5, 0.54, 0.58, 0.61],
                    [0.61, 0.645, 0.7, 0.73], [0.73, 0.765, 0.82, 0.85], [0.85, 0.885, 2, 3]];
    const SPOTS = [["mics", 0.6, 0.72], ["level", 0.72, 0.84], ["toggles", 0.84, 0.97]];
    const middle = (r) => [r[0] + r[2] / 2, r[1] + r[3] / 2];
    const dark = matchMedia("(prefers-color-scheme: dark)");
    let stages = [];
    let vw = 0, vh = 0, dpr = 1;
    let cam = { x: 0, y: 0, s: 1 };            // where the panel's (0, 0) lands, in CSS pixels, and its scale
    let mix = 0, mixFrom = 0, mixTo = 0, mixStart = 0, dipStart = -1;   // live 0 … muted 1, and the press
    let spot = null, spotAlpha = 0;
    let plate = null;                             // the colour around the mute button, read from its picture

    // The pictures come from <picture> elements, so the browser picks light or dark (and swaps on a change).
    const pictures = {};
    const usable = (img) => img && img.complete && img.naturalWidth > 0;
    scene.querySelectorAll("[data-layer] img").forEach((img) => {
      pictures[img.closest("[data-layer]").dataset.layer] = img;
      const ready = () => (img.decode ? img.decode() : Promise.resolve()).catch(() => {}).then(() => { plate = null; request(); });
      img.addEventListener("load", ready);
      if (usable(img)) ready();
    });

    const measure = () => {
      vw = pin.clientWidth;
      vh = pin.clientHeight;
      // The screen's own resolution, kept under about 16 megapixels on very large displays.
      dpr = Math.min(window.devicePixelRatio || 1, 3, Math.sqrt(16e6 / Math.max(1, vw * vh)));
      canvas.width = Math.round(vw * dpr);
      canvas.height = Math.round(vh * dpr);
      if (!L.head) return;
      const head = L.head, foot = L.footer, mute = L.mute;
      // The popover itself, without its shadow: what "the whole panel" means for framing.
      const box = [head[0] - 11, head[1] - 23, head[2] + 22, foot[1] + foot[3] + 34 - head[1]];
      const whole = middle(box);
      const top = parseFloat(getComputedStyle(caps[1]).top) || 90;
      const band = Math.min(vh * 0.44, top + Math.max(...caps.slice(1).map((c) => c.offsetHeight)) + 40);
      pin.style.setProperty("--band", `${Math.round(band)}px`);
      const heroBottom = top + caps[0].offsetHeight;
      const fit = Math.min((vh - band - 36) / box[3], (vw - 40) / box[2], 1.6);
      // The press: wide windows show the whole mute part, narrow ones the button with as much of its label as fits
      // (the label sits right of the button, or left in right-to-left languages).
      let zoomMute = Math.min((vw - 64) / head[2], (vh - band - 48) / head[3], 4.4);
      let pressAt = middle(head);
      if (zoomMute < 2.6) {
        zoomMute = Math.min(4.4, Math.max(fit * 2.2, (0.36 * Math.min(vw, vh)) / mute[2]));
        const seen = vw / zoomMute, lead = mute[2] / 2 + 16;
        const [hx] = middle(head), [bx, by] = middle(mute);
        pressAt = [bx < hx ? Math.min(hx, bx - lead + seen / 2) : Math.max(hx, bx + lead - seen / 2), by];
      }
      const y = band + (vh - band) / 2;
      const peek = clamp(vh - heroBottom - 28, 0, 150);
      const aim = (name) => {
        const r = L[name];
        return [middle(r), Math.min(fit * 1.9, (vw - 40) / (r[2] + 40), (vh - band - 40) / (r[3] + 40))];
      };
      const [mics, zMics] = aim("mics");
      const [level, zLevel] = aim("level");
      const [toggles, zToggles] = aim("toggles");
      stages = [
        [0, whole, vw / 2, vh - peek + (box[3] * fit) / 2, fit],
        [0.12, whole, vw / 2, y, fit],
        [0.26, pressAt, vw / 2, y, zoomMute],
        [0.4, pressAt, vw / 2, y, zoomMute],
        [0.52, whole, vw / 2, y, fit],
        [0.57, whole, vw / 2, y, fit],
        [0.63, mics, vw / 2, y, zMics],
        [0.69, mics, vw / 2, y, zMics],
        [0.75, level, vw / 2, y, zLevel],
        [0.81, level, vw / 2, y, zLevel],
        [0.87, toggles, vw / 2, y, zToggles],
        [0.94, toggles, vw / 2, y, zToggles],
        [1, whole, vw / 2, y, fit],
      ];
    };

    const place = (p) => {
      let i = 0;
      while (i < stages.length - 2 && p > stages[i + 1][0]) i++;
      const [p0, f0, x0, y0, s0] = stages[i];
      const [p1, f1, x1, y1, s1] = stages[i + 1];
      const t = ease(clamp((p - p0) / (p1 - p0)));
      const s = s0 * Math.pow(s1 / s0, t);
      const fx = f0[0] + (f1[0] - f0[0]) * t, fy = f0[1] + (f1[1] - f0[1]) * t;
      cam = { x: x0 + (x1 - x0) * t - fx * s, y: y0 + (y1 - y0) * t - fy * s, s };
    };

    // A picture over part of the panel (rect in panel points), optionally cut from its pixels (src).
    const put = (name, rect, alpha = 1, src = null) => {
      const img = pictures[name];
      if (!usable(img) || alpha <= 0) return;
      ctx.globalAlpha = alpha;
      if (src) ctx.drawImage(img, src[0], src[1], src[2], src[3], rect[0], rect[1], rect[2], rect[3]);
      else ctx.drawImage(img, rect[0], rect[1], rect[2], rect[3]);
      ctx.globalAlpha = 1;
    };
    // The pixels of a picture that covers `area` (panel points) which show the rect `r` of the panel.
    const cut = (name, area, r) => {
      const img = pictures[name];
      const f = usable(img) ? img.naturalWidth / area[2] : 1;
      return [(r[0] - area[0]) * f, (r[1] - area[1]) * f, r[2] * f, r[3] * f];
    };
    const whole = () => [0, 0, L.size[0], L.size[1]];
    const around = (r) => [r[0] - 4, r[1] - 4, r[2] + 8, r[3] + 8];
    // The close-ups cover the popover in three bands (top, call row, the rest) that meet without overlapping,
    // so its shadow is never drawn twice.
    const bands = () => {
      const a = L.crop, b = L.callCrop, c = L.lower;
      const y1 = a[1] + a[3], y2 = b[1] + b[3];
      return [["head-live", a, [a[0], a[1], a[2], a[3]]], ["call-live", b, [b[0], y1, b[2], y2 - y1]],
              ["lower", c, [c[0], y2, c[2], c[1] + c[3] - y2]]];
    };
    const sharpReady = () => ["head-live", "call-live", "lower"].every((name) => usable(pictures[name]));
    // What changes when muted (the mute part and the call row), faded in over the live picture.
    const drawMuted = (close) => {
      if (mix <= 0) return;
      const head = around(L.head), call = around(L.call);
      if (close && usable(pictures["head-muted"]) && usable(pictures["call-muted"])) {
        put("head-muted", head, mix, cut("head-muted", L.crop, head));
        put("call-muted", call, mix, cut("call-muted", L.callCrop, call));
      } else {
        put("panel-muted", head, mix, cut("panel-muted", whole(), head));
        put("panel-muted", call, mix, cut("panel-muted", whole(), call));
      }
    };
    // The colour of the plate the mute button sits on, read once from the picture right next to the button.
    const plateColor = () => {
      if (plate) return plate;
      const img = pictures["head-live"];
      if (!usable(img)) return null;
      const [mx, my, mw, mh] = L.mute;
      const beside = mx < L.head[0] + L.head[2] / 2 ? mx + mw + 7 : mx - 7;   // the label side is left in RTL
      const [sx, sy] = cut("head-live", L.crop, [beside, my + mh / 2, 1, 1]);
      const probe = d.createElement("canvas");
      probe.width = probe.height = 1;
      const pc = probe.getContext("2d", { willReadFrequently: true });
      pc.drawImage(img, sx, sy, 1, 1, 0, 0, 1, 1);
      const [r, g, b] = pc.getImageData(0, 0, 1, 1).data;
      plate = `rgb(${r}, ${g}, ${b})`;
      return plate;
    };
    // The press: only the button dips, like a real click.
    const press = (scale, close) => {
      const color = plateColor();
      if (!color) return;
      const [mx, my, mw, mh] = L.mute;
      const cx = mx + mw / 2, cy = my + mh / 2, r = mw / 2 + 9;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.clip();
      ctx.fillStyle = color;
      ctx.fillRect(cx - r, cy - r, r * 2, r * 2);
      ctx.translate(cx, cy);
      ctx.scale(scale, scale);
      ctx.translate(-cx, -cy);
      const head = around(L.head);
      if (close) put("head-live", head, 1, cut("head-live", L.crop, head));
      else put("panel-live", head, 1, cut("panel-live", whole(), head));
      drawMuted(close);
      ctx.restore();
    };
    const roundRect = (x, y, w, h, r) => {
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    };

    const draw = (now) => {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!usable(pictures["panel-live"])) return;
      const k = dpr * cam.s;                      // device pixels per panel point
      ctx.setTransform(k, 0, 0, k, dpr * cam.x, dpr * cam.y);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      // Closer than the 2x picture holds: the 8x and 4x close-ups take over the popover, and the 2x picture
      // only shows around them (the far shadow).
      const close = k > 2.3 && sharpReady();
      if (close) {
        const a = L.crop, c = L.lower;
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, L.size[0], L.size[1]);
        ctx.rect(a[0], a[1], a[2], c[1] + c[3] - a[1]);
        ctx.clip("evenodd");
        put("panel-live", whole());
        ctx.restore();
        for (const [name, area, r] of bands()) put(name, r, 1, cut(name, area, r));
      } else {
        put("panel-live", whole());
      }
      drawMuted(close);
      const t = dipStart < 0 ? 1 : clamp((now - dipStart) / 520);
      if (t < 1) press(t < 0.3 ? 1 - 0.05 * ease(t / 0.3) : 0.95 + 0.05 * ease((t - 0.3) / 0.7), close);
      // Guided tour: everything but one part fades back.
      if (spot && spotAlpha > 0.001) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.beginPath();
        ctx.rect(0, 0, canvas.width, canvas.height);
        roundRect(dpr * cam.x + k * (spot[0] - 5), dpr * cam.y + k * (spot[1] - 5), k * (spot[2] + 10), k * (spot[3] + 10), k * 16);
        ctx.globalAlpha = spotAlpha;
        ctx.fillStyle = dark.matches ? "rgba(0, 0, 0, .86)" : "rgba(255, 255, 255, .86)";
        ctx.fill("evenodd");
        ctx.globalAlpha = 1;
      }
    };
    if (dark.addEventListener) dark.addEventListener("change", () => { plate = null; request(); });

    parts.push({
      measure,
      update(now) {
        if (!stages.length) return false;
        const r = pin.getBoundingClientRect();
        if (r.bottom <= 0 || r.top >= innerHeight) return false;   // out of view: nothing to draw
        const p = progress(cinema, vh);
        place(p);
        const want = p >= 0.33 ? 1 : 0;
        if (want !== mixTo) {
          mixFrom = mix;
          mixTo = want;
          mixStart = now;
          dipStart = want ? now : -1;
        }
        const tm = clamp((now - mixStart) / 280);
        mix = mixFrom + (mixTo - mixFrom) * ease(tm);
        spot = null;
        spotAlpha = 0;
        for (const [name, a, b] of SPOTS) {
          const o = Math.min(smooth(a, a + 0.025, p), 1 - smooth(b - 0.025, b, p));
          if (o > spotAlpha && L[name]) { spotAlpha = o; spot = L[name]; }
        }
        caps.forEach((cap, i) => {
          const [a, b, c, e] = RANGES[i] || [2, 3, 4, 5];
          const o = i === 0 ? 1 - smooth(c, e, p) : Math.min(smooth(a, b, p), 1 - smooth(c, e, p));
          cap.style.opacity = o.toFixed(3);
          cap.style.transform = `translateY(${((1 - o) * (i === 0 ? -24 : 22)).toFixed(1)}px)`;
          cap.style.visibility = o < 0.01 ? "hidden" : "visible";
          cap.style.pointerEvents = o > 0.5 ? "auto" : "none";
        });
        draw(now);
        return tm < 1 || (dipStart >= 0 && now - dipStart < 520);   // still fading or pressing: keep drawing
      },
    });
  }

  // ---------- Settings tour: plays by itself, pane by pane ----------
  // Each pane stays six seconds while the bar beside its step fills; a click or tap picks one, and pointing
  // at the steps holds the one on screen.
  const tour = d.querySelector(".tour");
  if (tour && motion) {
    const steps = [...tour.querySelectorAll(".ts")];
    const shots = [...tour.querySelectorAll(".tf")];
    const dots = [...tour.querySelectorAll(".tour-dots button")];
    const DURATION = 6000;
    let current = 0, elapsed = 0, last = 0, visible = !observe, held = false, ticking = 0;
    const show = (i) => {
      current = i;
      elapsed = 0;
      [steps, shots, dots].forEach((list) => list.forEach((el, k) => el.classList.toggle("on", k === i)));
      steps.forEach((el, k) => el.setAttribute("aria-selected", String(k === i)));
      tour.style.setProperty("--tour-p", "0");
    };
    const tick = (now) => {
      ticking = 0;
      if (!visible) return;
      if (!held && last) elapsed += Math.min(500, now - last);
      last = now;
      if (elapsed >= DURATION) show((current + 1) % steps.length);
      tour.style.setProperty("--tour-p", (elapsed / DURATION).toFixed(4));
      ticking = requestAnimationFrame(tick);
    };
    steps.forEach((el, i) => {
      el.addEventListener("click", () => show(i));
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); show(i); }
      });
    });
    dots.forEach((el, i) => el.addEventListener("click", () => show(i)));
    const list = tour.querySelector(".tour-text");
    list.addEventListener("pointerenter", (ev) => { if (ev.pointerType === "mouse") held = true; });
    list.addEventListener("pointerleave", () => { held = false; });
    d.addEventListener("visibilitychange", () => { last = 0; });   // no jump after the tab was in the background
    if (observe) {
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        last = 0;
        if (visible && !ticking) ticking = requestAnimationFrame(tick);
      }, { threshold: 0.35 }).observe(tour);
    } else {
      ticking = requestAnimationFrame(tick);
    }
    show(0);
  }

  // ---------- Statement: words light up as it scrolls past ----------
  const words = d.querySelector(".words");
  if (words && motion) {
    const spans = [...words.querySelectorAll(".w")];
    let lit = -1;
    parts.push({
      update() {
        const r = words.getBoundingClientRect();
        const p = clamp((innerHeight * 0.86 - r.top) / (r.height + innerHeight * 0.4));
        const n = Math.round(p * spans.length);
        if (n === lit) return;
        lit = n;
        spans.forEach((span, i) => span.classList.toggle("lit", i < n));
      },
    });
  }

  // ---------- Features: the strip slides sideways while the page scrolls down ----------
  const rail = d.querySelector(".rail");
  if (rail && motion) {
    const railPin = rail.querySelector(".rail-pin");
    const track = rail.querySelector(".rail-track");
    let overflow = 0, pinHeight = 0;
    parts.push({
      measure() {
        track.style.transform = "";
        pinHeight = railPin.clientHeight || innerHeight;
        overflow = Math.max(0, track.scrollWidth - railPin.clientWidth);
        rail.style.height = `${pinHeight + overflow}px`;
      },
      update() {
        const p = progress(rail, pinHeight);
        track.style.transform = `translate3d(${((rtl ? 1 : -1) * p * overflow).toFixed(1)}px, 0, 0)`;
      },
    });
  }

  // ---------- Finale: the icon pops in and the words follow, once it comes into view ----------
  const final = d.querySelector(".final");
  if (final && motion) {
    if (!observe) {
      final.classList.add("go");
    } else {
      const seen = new IntersectionObserver(([entry]) => {
        if (!entry.isIntersecting) return;
        final.classList.add("go");
        seen.disconnect();
      }, { threshold: 0.35 });
      seen.observe(final);
    }
  }

  // ---------- Language: remember the one picked, so the home page opens in it next time ----------
  d.querySelectorAll("footer .langs a[hreflang]").forEach((a) => a.addEventListener("click", () => {
    try { localStorage.setItem("muffle-lang", a.getAttribute("hreflang").toLowerCase()); } catch (err) { /* storage off */ }
  }));

  // ---------- Counters ----------
  const counters = d.querySelectorAll("[data-count]");
  if (motion && observe) {
    const format = new Intl.NumberFormat(root.lang);
    counters.forEach((el) => { if (Number(el.dataset.count) > 0) el.textContent = format.format(0); });
    const count = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      count.unobserve(entry.target);
      const el = entry.target;
      const end = Number(el.dataset.count);
      if (!(end > 0)) return;
      const start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / 1400);
        el.textContent = format.format(Math.round(end * (1 - Math.pow(1 - t, 3))));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }), { threshold: 0.5 });
    counters.forEach((el) => count.observe(el));
  }

  // ---------- One loop for everything ----------
  let queued = false;
  const frame = (now = performance.now()) => {
    queued = false;
    updateNav();
    let again = false;
    parts.forEach((part) => { if (part.update && part.update(now)) again = true; });
    if (again) request();
  };
  const request = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(frame);
  };
  const remeasure = () => {
    parts.forEach((part) => part.measure && part.measure());
    frame();   // draw right away: animation frames wait while a tab is in the background
  };
  addEventListener("scroll", request, { passive: true });
  addEventListener("resize", remeasure);
  addEventListener("load", remeasure);
  if (d.fonts && d.fonts.ready) d.fonts.ready.then(remeasure);
  remeasure();
})();
