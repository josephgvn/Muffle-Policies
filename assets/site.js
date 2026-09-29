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

  // ---------- Opening: the panel rises, the page zooms into its mute button, presses it, zooms back out ----------
  const cinema = d.querySelector(".cinema");
  if (cinema) {
    const pin = cinema.querySelector(".cinema-pin");
    const scene = cinema.querySelector(".scene");
    const button = scene.querySelector(".mute");
    const caps = [...cinema.querySelectorAll(".cap")];
    // When each caption fades in and out: the headline, "One press", "Every control".
    const RANGES = [[0, 0, 0.03, 0.09], [0.2, 0.26, 0.5, 0.56], [0.6, 0.66, 2, 3]];
    let stages = [];
    let vw = 0, vh = 0;

    const measure = () => {
      vw = pin.clientWidth;
      vh = pin.clientHeight;
      if (!motion) {
        scene.classList.add("is-muted");
        return;
      }
      const W = scene.offsetWidth, H = scene.offsetHeight;
      const center = [W / 2, H / 2];
      const mute = [button.offsetLeft + button.offsetWidth / 2, button.offsetTop + button.offsetHeight / 2];
      const top = parseFloat(getComputedStyle(caps[1]).top) || 90;
      const band = Math.min(vh * 0.42, top + Math.max(...caps.slice(1).map((c) => c.offsetHeight)) + 28);
      pin.style.setProperty("--band", `${Math.round(band)}px`);
      const heroBottom = top + caps[0].offsetHeight;
      const fit = Math.min((vh - band - 40) / H, (vw - 48) / W, 1.5);
      const zoom = Math.max(fit * 2.2, (0.36 * Math.min(vw, vh)) / button.offsetWidth);
      const y = band + (vh - band) / 2;
      // Under the headline the panel only peeks out, if there is room for it.
      const peek = clamp(vh - heroBottom - 28, 0, 150);
      stages = [
        [0, center, vw / 2, vh - peek + (H * fit) / 2, fit],
        [0.13, center, vw / 2, y, fit],
        [0.32, mute, vw / 2, y, zoom],
        [0.46, mute, vw / 2, y, zoom],
        [0.64, center, vw / 2, y, fit],
        [1, center, vw / 2, y, fit],
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
        if (!motion) return;
        const p = progress(cinema, vh);
        place(p);
        scene.classList.toggle("is-muted", p >= 0.37);
        pin.style.setProperty("--hint", (1 - smooth(0, 0.03, p)).toFixed(3));
        caps.forEach((cap, i) => {
          const [a, b, c, e] = RANGES[i];
          const o = i === 0 ? 1 - smooth(c, e, p) : Math.min(smooth(a, b, p), 1 - smooth(c, e, p));
          cap.style.opacity = o.toFixed(3);
          cap.style.transform = `translateY(${((1 - o) * (i === 0 ? -24 : 22)).toFixed(1)}px)`;
          cap.style.visibility = o < 0.01 ? "hidden" : "visible";
          cap.style.pointerEvents = o > 0.5 ? "auto" : "none";
        });
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
