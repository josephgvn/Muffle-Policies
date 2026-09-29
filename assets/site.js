/* Muffle website: reveal on scroll, the pinned story, counters and a little parallax.
   Everything on the page reads fine without it. */
(() => {
  const d = document;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const observe = "IntersectionObserver" in window;

  const nav = d.querySelector(".nav");
  const onScroll = () => nav && nav.classList.toggle("scrolled", scrollY > 8);
  addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  const reveals = d.querySelectorAll(".reveal");
  const showAll = () => reveals.forEach((el) => el.classList.add("in"));
  if (reduce || !observe) {
    showAll();
  } else {
    const seen = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      seen.unobserve(entry.target);
    }), { rootMargin: "0px 0px -6% 0px", threshold: 0.1 });
    reveals.forEach((el) => seen.observe(el));
    // Safety net: a browser that never reports visibility (some renderers and crawlers) still gets every word.
    setTimeout(() => { if (!d.querySelector(".reveal.in")) showAll(); }, 2500);
    addEventListener("beforeprint", showAll);
  }

  const story = d.querySelector(".story");
  if (story) {
    const steps = [...story.querySelectorAll(".story-step")];
    const frames = [...story.querySelectorAll(".story-frame")];
    const show = (step) => {
      steps.forEach((el) => el.classList.toggle("on", el.dataset.step === step));
      frames.forEach((el) => el.classList.toggle("on", el.dataset.step === step));
    };
    show("0");
    if (observe) {
      const middle = new IntersectionObserver((entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) show(entry.target.dataset.step);
      }), { rootMargin: "-45% 0px -45% 0px" });
      steps.forEach((el) => middle.observe(el));
    }
  }

  const counters = d.querySelectorAll("[data-count]");
  if (!reduce && observe) {
    const format = new Intl.NumberFormat(d.documentElement.lang);
    counters.forEach((el) => { if (Number(el.dataset.count) > 0) el.textContent = format.format(0); });
    const count = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      count.unobserve(entry.target);
      const el = entry.target;
      const end = Number(el.dataset.count);
      if (!(end > 0)) return;
      const start = performance.now();
      const tick = (now) => {
        const progress = Math.min(1, (now - start) / 1400);
        el.textContent = format.format(Math.round(end * (1 - Math.pow(1 - progress, 3))));
        if (progress < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }), { threshold: 0.5 });
    counters.forEach((el) => count.observe(el));
  }

  const floats = d.querySelectorAll("[data-parallax]");
  if (!reduce && floats.length) {
    let queued = false;
    const move = () => {
      queued = false;
      const y = Math.min(scrollY, 1400);
      floats.forEach((el) => el.style.setProperty("--py", (y * Number(el.dataset.parallax)).toFixed(1) + "px"));
    };
    addEventListener("scroll", () => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(move);
    }, { passive: true });
  }
})();
