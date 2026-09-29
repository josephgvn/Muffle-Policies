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

  // ---------- Opening scene ----------
  const cinema = d.querySelector(".cinema");
  if (cinema) {
    const pin = cinema.querySelector(".cinema-pin");
    const view = cinema.querySelector(".cinema-view");
    const scene = cinema.querySelector(".scene");
    const caps = [...cinema.querySelectorAll(".cap")];
    const hero = caps[0];
    // Scene points the camera looks at.
    const ICON = [1236, 16], PANEL = [1236, 318], SCREEN = [720, 450], PRESS = [1110, 392], CALL = [600, 520];
    // When each caption fades in and out.
    const RANGES = [[0, 0, 0.02, 0.08], [0.19, 0.24, 0.35, 0.4], [0.43, 0.48, 0.56, 0.6], [0.62, 0.66, 0.77, 0.81], [0.82, 0.86, 2, 3]];
    let stages = [];
    let vw = 0, vh = 0;

    const measure = () => {
      vw = pin.clientWidth;
      vh = pin.clientHeight;
      if (!motion) {
        const fit = Math.min(1, (view.clientWidth - 48) / 1440);
        scene.style.setProperty("--fit", fit.toFixed(4));
        scene.classList.add("is-open", "is-muted");
        scene.style.setProperty("--pod", "1");
        return;
      }
      const wide = vw >= 980 && vh >= 560;
      cinema.classList.toggle("wide", wide);
      const top = parseFloat(getComputedStyle(caps[2]).top) || 90;
      const band = Math.min(vh * 0.4, top + Math.max(...caps.slice(wide ? 2 : 1).map((c) => c.offsetHeight)) + 24);
      const heroBottom = top + hero.offsetHeight;   // used for the top fade
      const fit = Math.min((vw - 32) / 1440, (vh - band - 20) / 900);
      // The giant icon waits just below the screen, then rises into the middle once the headline has gone.
      const iconSize = clamp(0.42 * Math.min(vw, vh), 120, 420);
      const yIcon = vh * 0.56;
      const yIconStart = vh + iconSize * 0.62;
      const yBelow = band + (vh - band) / 2;
      pin.style.setProperty("--band", `${Math.round(Math.max(band, heroBottom * 0.55))}px`);
      // Wide screens: the panel caption sits on the left and the panel fills the right half.
      if (wide) caps[1].style.top = `${Math.max(80, (vh - caps[1].offsetHeight) / 2)}px`;
      else caps[1].style.top = "";
      const panelScale = wide ? Math.min((vh - 110) / 590, (vw * 0.46) / 356) : Math.min((vh - band - 36) / 590, (vw - 40) / 356);
      const panelX = wide ? vw * (rtl ? 0.34 : 0.66) : vw / 2;
      const panelY = wide ? vh / 2 + 24 : yBelow;
      stages = [
        [0, ICON, vw / 2, yIconStart, iconSize / 17],
        [0.09, ICON, vw / 2, yIcon, iconSize / 17],
        [0.13, ICON, vw / 2, yIcon, iconSize / 17],
        [0.3, PANEL, panelX, panelY, panelScale],
        [0.47, SCREEN, vw / 2, yBelow, fit],
        [0.57, SCREEN, vw / 2, yBelow, fit],
        [0.66, PRESS, vw / 2, yBelow, Math.min(fit * 1.55, (vh - band - 10) / 700)],
        [0.78, PRESS, vw / 2, yBelow, Math.min(fit * 1.55, (vh - band - 10) / 700)],
        [0.88, CALL, vw / 2, yBelow, fit * 1.3],
        [1, CALL, vw / 2, yBelow, fit * 1.3],
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
        scene.style.setProperty("--open", smooth(0.12, 0.24, p).toFixed(3));
        scene.style.setProperty("--pod", smooth(0.58, 0.66, p).toFixed(3));
        scene.style.setProperty("--press", (smooth(0.66, 0.69, p) * (1 - smooth(0.7, 0.76, p))).toFixed(3));
        scene.classList.toggle("is-open", p > 0.12);
        scene.classList.toggle("is-muted", p >= 0.69);
        scene.classList.toggle("is-talking", p >= 0.845);
        pin.style.setProperty("--hint", (1 - smooth(0, 0.03, p)).toFixed(3));
        caps.forEach((cap, i) => {
          const [a, b, c, e] = RANGES[i];
          const o = i === 0 ? 1 - smooth(c, e, p) : Math.min(smooth(a, b, p), 1 - smooth(c, e, p));
          cap.style.opacity = o.toFixed(3);
          cap.style.transform = `translateY(${((1 - o) * (i === 0 ? -24 : 22)).toFixed(1)}px)`;
          cap.style.visibility = o < 0.01 ? "hidden" : "visible";
          cap.style.pointerEvents = o > 0.5 ? "auto" : "none";
          if (i === 1) {
            // The side caption brings its own backdrop; the top fade steps aside so the panel stays clear.
            const side = cinema.classList.contains("wide") ? o : 0;
            pin.style.setProperty("--side", side.toFixed(3));
            pin.style.setProperty("--scrim", (1 - side).toFixed(3));
          }
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
