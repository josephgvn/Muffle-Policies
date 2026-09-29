/* Muffle website motion. The page reads fine without any of it: with no script, or with reduced motion,
   everything shows in its final state. */
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

  // ---------- Opening: a guided tour of the real panel ----------
  // The panel rises, the page zooms into the mute button and presses it, zooms back out,
  // then points at the microphones, the level and the quick switches in turn.
  const cinema = d.querySelector(".cinema");
  if (cinema) {
    const pin = cinema.querySelector(".cinema-pin");
    const scene = cinema.querySelector(".scene");
    const spot = scene.querySelector(".spot");
    const caps = [...cinema.querySelectorAll(".cap")];
    const layout = JSON.parse(scene.dataset.parts || "{}");
    // Captions: headline, one press, every control, microphones, level, switches.
    const RANGES = [[0, 0, 0.03, 0.09], [0.09, 0.14, 0.44, 0.49], [0.5, 0.54, 0.58, 0.61],
                    [0.61, 0.645, 0.7, 0.73], [0.73, 0.765, 0.82, 0.85], [0.85, 0.885, 2, 3]];
    const SPOTS = [["mics", 0.6, 0.72], ["level", 0.72, 0.84], ["toggles", 0.84, 0.97]];
    const middle = (r) => [r[0] + r[2] / 2, r[1] + r[3] / 2];
    let stages = [];
    let vw = 0, vh = 0;

    const measure = () => {
      vw = pin.clientWidth;
      vh = pin.clientHeight;
      if (!motion || !layout.head) return;   // without motion the page shows a still picture instead
      const head = layout.head, foot = layout.footer, mute = layout.mute;
      // The popover itself, without its shadow: what "the whole panel" means for framing.
      const box = [head[0] - 11, head[1] - 23, head[2] + 22, foot[1] + foot[3] + 34 - head[1]];
      const whole = middle(box);
      const top = parseFloat(getComputedStyle(caps[1]).top) || 90;
      const band = Math.min(vh * 0.44, top + Math.max(...caps.slice(1).map((c) => c.offsetHeight)) + 40);
      pin.style.setProperty("--band", `${Math.round(band)}px`);
      const heroBottom = top + caps[0].offsetHeight;
      const fit = Math.min((vh - band - 36) / box[3], (vw - 40) / box[2], 1.6);
      // The press: wide windows show the whole mute part, narrow ones the button with as much of its label as fits
      // (the label sits right of the button, or left in right-to-left languages). 4.4 is as far as the 8x
      // close-up stays sharp on a Retina screen.
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
        const r = layout[name];
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
      const sx = x0 + (x1 - x0) * t, sy = y0 + (y1 - y0) * t;
      scene.style.transform = `translate3d(${(sx - fx * s).toFixed(1)}px, ${(sy - fy * s).toFixed(1)}px, 0) scale(${s.toFixed(4)})`;
    };

    parts.push({
      measure,
      update() {
        if (!motion || !stages.length) return;
        const p = progress(cinema, vh);
        place(p);
        scene.classList.toggle("is-muted", p >= 0.33);
        let shown = 0, target = null;
        for (const [name, a, b] of SPOTS) {
          const o = Math.min(smooth(a, a + 0.025, p), 1 - smooth(b - 0.025, b, p));
          if (o > shown) { shown = o; target = name; }
        }
        if (target && layout[target]) {
          const r = layout[target];
          spot.style.left = `${r[0] - 5}px`;
          spot.style.top = `${r[1] - 5}px`;
          spot.style.width = `${r[2] + 10}px`;
          spot.style.height = `${r[3] + 10}px`;
        }
        spot.style.opacity = shown.toFixed(3);
        caps.forEach((cap, i) => {
          const [a, b, c, e] = RANGES[i] || [2, 3, 4, 5];
          const o = i === 0 ? 1 - smooth(c, e, p) : Math.min(smooth(a, b, p), 1 - smooth(c, e, p));
          cap.style.opacity = o.toFixed(3);
          cap.style.transform = `translateY(${((1 - o) * (i === 0 ? -24 : 22)).toFixed(1)}px)`;
          cap.style.visibility = o < 0.01 ? "hidden" : "visible";
          cap.style.pointerEvents = o > 0.5 ? "auto" : "none";
        });
      },
    });
  }

  // ---------- Settings tour: the window changes pane as the page scrolls ----------
  const tour = d.querySelector(".tour");
  if (tour && motion) {
    const tourPin = tour.querySelector(".tour-pin");
    const texts = [...tour.querySelectorAll(".ts")];
    const shots = [...tour.querySelectorAll(".tf")];
    let current = -1;
    texts.forEach((el, i) => el.addEventListener("click", () => {
      const run = tour.offsetHeight - (tourPin.clientHeight || innerHeight);
      scrollTo({ top: tour.offsetTop + run * ((i + 0.5) / texts.length), behavior: "smooth" });
    }));
    parts.push({
      update() {
        const p = progress(tour, tourPin.clientHeight || innerHeight);
        const step = Math.min(texts.length - 1, Math.floor(p * texts.length));
        if (step === current) return;
        current = step;
        texts.forEach((el, i) => el.classList.toggle("on", i === step));
        shots.forEach((el, i) => el.classList.toggle("on", i === step));
      },
    });
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

  // ---------- Finale: the icon grows and turns into place ----------
  const final = d.querySelector(".final");
  if (final && motion) {
    const finalPin = final.querySelector(".final-pin");
    parts.push({
      update() {
        const p = progress(final, finalPin.clientHeight || innerHeight);
        const grow = ease(smooth(0, 0.55, p));
        final.style.setProperty("--icon-s", (0.5 + 0.5 * grow).toFixed(3));
        final.style.setProperty("--icon-r", `${((1 - grow) * -20).toFixed(1)}deg`);
        final.style.setProperty("--final-o", smooth(0.2, 0.5, p).toFixed(3));
      },
    });
  }

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
  const frame = () => {
    queued = false;
    updateNav();
    parts.forEach((part) => part.update && part.update());
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
