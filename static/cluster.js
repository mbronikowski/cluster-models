/* Cluster pages: copy-coordinates button and the Aladin Lite sky view (loaded on demand). */
(() => {
  "use strict";

  for (const btn of document.querySelectorAll("button[data-copy]")) {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy;
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const ta = Object.assign(document.createElement("textarea"), { value: text });
        document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove();
      }
      const old = btn.textContent;
      btn.textContent = "Copied";
      btn.classList.add("is-done");
      setTimeout(() => { btn.textContent = old; btn.classList.remove("is-done"); }, 1600);
    });
  }

  const box = document.querySelector("[data-aladin]");
  if (!box) return;
  const target = box.querySelector(".aladin-target");
  const ra = parseFloat(box.dataset.ra), dec = parseFloat(box.dataset.dec);

  function fail(reason) {
    const p = document.createElement("p");
    p.textContent = `The sky view could not be shown (${reason}). `;
    const a = document.createElement("a");
    a.href = `https://sky.esa.int/esasky/?target=${encodeURIComponent(`${ra.toFixed(5)} ${dec.toFixed(5)}`)}&fov=0.15&cooframe=J2000&sci=true`;
    a.textContent = "Open this position in ESASky";
    p.append(a, ".");
    const wrap = document.createElement("div");
    wrap.className = "aladin-placeholder";
    wrap.append(p);
    target.replaceChildren(wrap);
  }

  function start() {
    if (box.dataset.started) return;
    box.dataset.started = "1";
    target.replaceChildren();
    const s = document.createElement("script");
    s.src = box.dataset.src;
    s.charset = "utf-8";
    s.async = true;
    s.onerror = () => fail("Aladin Lite did not load");
    s.onload = () => {
      window.A.init.then(() => {
        const survey = dec > -29 ? "CDS/P/PanSTARRS/DR1/color-z-zg-g"
          : dec > -65 ? "CDS/P/DESI-Legacy-Surveys/DR10/color" : "CDS/P/DSS2/color";
        const aladin = window.A.aladin(target, {
          survey, fov: 0.1, target: `${ra} ${dec}`, cooFrame: "ICRSd",
          showReticle: false, showZoomControl: true, showFullscreenControl: true,
          showLayersControl: true, showGotoControl: false, showShareControl: false,
          showSimbadPointerControl: true, showCooGridControl: true, showProjectionControl: false,
          showFrame: true, showContextMenu: true,
        });
        const cat = window.A.catalog({ name: "Catalogue position", sourceSize: 18, color: "#e6ac3c", shape: "plus" });
        aladin.addCatalog(cat);
        cat.addSources([window.A.marker(ra, dec, { popupTitle: box.dataset.name, popupDesc: "Position in this catalogue" })]);
      }).catch((err) => fail(String(err).includes("WebGL") ? "your browser has no WebGL2" : "Aladin Lite failed to start"));
    };
    document.head.append(s);
  }

  box.querySelector("[data-aladin-load]")?.addEventListener("click", start);
  // Load automatically on wide screens once the viewer scrolls into view.
  if (window.matchMedia("(min-width: 960px)").matches && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); start(); }
    }, { rootMargin: "100px" });
    io.observe(box);
  }
})();
