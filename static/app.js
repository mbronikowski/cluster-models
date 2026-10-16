/* Landing page: name and cone search, filters, sortable table, sky map, CSV export.
   The table and map are rendered on the server; this script only filters and orders them. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const data = JSON.parse($("cluster-index").textContent);
  const table = $("cluster-table");
  const tbody = table.tBodies[0];
  const rows = new Map([...tbody.rows].map((tr) => [tr.dataset.slug, tr]));
  const dotsGroup = $("sky-dots");
  const dots = new Map([...dotsGroup.querySelectorAll(".dot")].map((a) => [a.dataset.slug, a]));
  const coneGroup = $("sky-cone");
  const tip = $("sky-tip");
  const fields = {
    q: $("q"), r: $("r"), zmin: $("zmin"), zmax: $("zmax"),
    program: $("program"), cat: $("cat"), pub: $("pub"), jw: $("jw"), tr: $("tr"),
  };
  const collator = new Intl.Collator("en", { numeric: true, sensitivity: "base" });
  const SVGNS = "http://www.w3.org/2000/svg";
  let sort = { key: "name", dir: 1, auto: true };
  let shown = data.map((d) => ({ d, sep: null, rank: 0 }));

  /* ---- name normalisation: mirrors cmdb.catalogues.search_key ---- */
  function normKey(s) {
    s = s.toUpperCase().replace(/[−–‐‑]/g, "-").replace(/[\s_]+/g, "");
    s = s.replace(/([A-Z])-(?=[A-Z])/g, "$1");
    s = s.replace(/^([A-Z][A-Z0-9]*?[A-Z])J(?=\d)/, "$1");
    s = s.replace(/^(?:ABELL|ACO)(?=S?\d)/, "A");
    s = s.replace(/^(AS?)0+(?=\d)/, "$1");
    return s;
  }
  function matchRank(d, k) {
    let best = 9;
    for (const key of d.k) {
      if (key === k) return 0;
      if (key.startsWith(k)) best = Math.min(best, 1);
      else if (key.includes(k)) best = Math.min(best, 2);
    }
    return best;
  }

  /* ---- coordinates ---- */
  function parseCoords(text) {
    let t = text.trim().replace(/[−–‐‑]/g, "-").replace(/,/g, " ");
    t = t.replace(/[hdms:°'"′″]/gi, " ").replace(/(\d)([+-])/g, "$1 $2");
    const p = t.split(/\s+/).filter(Boolean);
    if (!p.length || !p.every((x) => /^[+-]?\d+(\.\d+)?$/.test(x))) return null;
    let ra, dec;
    if (p.length === 2) {
      ra = +p[0]; dec = +p[1];
    } else if (p.length === 6) {
      const neg = p[3].startsWith("-");
      ra = 15 * (+p[0] + +p[1] / 60 + +p[2] / 3600);
      dec = (neg ? -1 : 1) * (Math.abs(+p[3]) + +p[4] / 60 + +p[5] / 3600);
    } else return null;
    if (!(ra >= 0 && ra < 360 && dec >= -90 && dec <= 90)) return null;
    return { ra, dec };
  }
  const rad = Math.PI / 180;
  function sepDeg(ra1, de1, ra2, de2) {
    const a = Math.sin(((de2 - de1) * rad) / 2) ** 2 +
      Math.cos(de1 * rad) * Math.cos(de2 * rad) * Math.sin(((ra2 - ra1) * rad) / 2) ** 2;
    return (2 * Math.asin(Math.min(1, Math.sqrt(a)))) / rad;
  }
  /* Mollweide, centred on RA = 6h, RA increasing leftwards: mirrors cmdb.site.mollweide */
  const W = 960, H = 480, CENTER = 90;
  function project(ra, dec) {
    const lam = ((((CENTER - ra) + 180) % 360 + 360) % 360 - 180) * rad;
    const phi = dec * rad;
    let th = phi;
    if (Math.abs(Math.abs(phi) - Math.PI / 2) > 1e-9) {
      for (let i = 0; i < 50; i++) {
        const f = 2 * th + Math.sin(2 * th) - Math.PI * Math.sin(phi);
        const d = 2 + 2 * Math.cos(2 * th);
        if (Math.abs(d) < 1e-12) break;
        const step = f / d; th -= step;
        if (Math.abs(step) < 1e-10) break;
      }
    }
    const x = (2 * Math.SQRT2 / Math.PI) * lam * Math.cos(th);
    const y = Math.SQRT2 * Math.sin(th);
    return [W / 2 + x * (W / 2) / (2 * Math.SQRT2), H / 2 - y * (H / 2) / Math.SQRT2];
  }
  function drawCone(pos, radiusArcmin) {
    coneGroup.replaceChildren();
    if (!pos) return;
    const r = (radiusArcmin / 60) * rad;
    const d0 = pos.dec * rad;
    const pts = [];
    for (let i = 0; i <= 96; i++) {
      const b = (i / 96) * 2 * Math.PI;
      const dec = Math.asin(Math.sin(d0) * Math.cos(r) + Math.cos(d0) * Math.sin(r) * Math.cos(b));
      const ra = pos.ra + Math.atan2(Math.sin(b) * Math.sin(r) * Math.cos(d0), Math.cos(r) - Math.sin(d0) * Math.sin(dec)) / rad;
      pts.push(project(((ra % 360) + 360) % 360, dec / rad));
    }
    const [cx, cy] = project(pos.ra, pos.dec);
    const span = Math.max(...pts.map((p) => Math.hypot(p[0] - cx, p[1] - cy)));
    if (span > 5 && span < W / 3) {
      const poly = document.createElementNS(SVGNS, "polygon");
      poly.setAttribute("points", pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" "));
      poly.setAttribute("class", "cone-ring");
      coneGroup.append(poly);
    }
    const g = 9, inner = 4;
    for (const [x1, y1, x2, y2] of [[cx - g, cy, cx - inner, cy], [cx + inner, cy, cx + g, cy], [cx, cy - g, cx, cy - inner], [cx, cy + inner, cx, cy + g]]) {
      const l = document.createElementNS(SVGNS, "line");
      l.setAttribute("x1", x1); l.setAttribute("y1", y1); l.setAttribute("x2", x2); l.setAttribute("y2", y2);
      l.setAttribute("class", "cone-mark");
      coneGroup.append(l);
    }
  }

  /* ---- filtering, sorting, rendering ---- */
  const num = (el) => (el.value.trim() === "" ? null : parseFloat(el.value));
  function compare(a, b) {
    const k = sort.key;
    let v;
    if (k === "name") v = collator.compare(a.d.n, b.d.n);
    else if (k === "ra") v = a.d.ra - b.d.ra;
    else if (k === "dec") v = a.d.dec - b.d.dec;
    else if (k === "z") v = a.d.z - b.d.z;
    else if (k === "models") v = a.d.m - b.d.m;
    else if (k === "sep") v = (a.sep ?? 1e9) - (b.sep ?? 1e9);
    return v * sort.dir || collator.compare(a.d.n, b.d.n);
  }
  function apply() {
    const text = fields.q.value.trim();
    const pos = parseCoords(text);
    const radius = Math.max(0.01, num(fields.r) ?? 10);
    const key = pos ? "" : normKey(text);
    const zmin = num(fields.zmin), zmax = num(fields.zmax);
    const prog = fields.program.value, cat = fields.cat.value;
    const out = [];
    for (const d of data) {
      let sep = null, rank = 0;
      if (pos) {
        sep = sepDeg(pos.ra, pos.dec, d.ra, d.dec) * 60;
        if (sep > radius) continue;
      } else if (key) {
        rank = matchRank(d, key);
        if (rank > 2) continue;
      }
      if (zmin !== null && !(d.z >= zmin)) continue;
      if (zmax !== null && !(d.z <= zmax)) continue;
      if (prog && !d.p.includes(prog)) continue;
      if (cat && !d.cat.includes(cat)) continue;
      if (fields.pub.checked && !d.pub) continue;
      if (fields.jw.checked && !d.jw) continue;
      if (fields.tr.checked && !d.t.length) continue;
      out.push({ d, sep, rank });
    }
    if (sort.auto) {
      if (pos) sort = { key: "sep", dir: 1, auto: true };
      else if (sort.key === "sep") sort = { key: "name", dir: 1, auto: true };
    }
    out.sort((a, b) => (key && !pos ? a.rank - b.rank : 0) || compare(a, b));
    shown = out;
    render(pos, radius);
    saveState();
  }
  function render(pos, radius) {
    const visible = new Set(shown.map((x) => x.d.s));
    const frag = document.createDocumentFragment();
    for (const x of shown) {
      const tr = rows.get(x.d.s);
      tr.hidden = false;
      tr.querySelector(".col-sep").textContent = x.sep === null ? "" : x.sep.toFixed(1);
      frag.append(tr);
    }
    for (const [slug, tr] of rows) if (!visible.has(slug)) { tr.hidden = true; frag.append(tr); }
    tbody.append(frag);
    for (const el of table.querySelectorAll(".col-sep")) el.hidden = !pos;
    for (const th of table.tHead.rows[0].cells) {
      const b = th.querySelector("button");
      if (b && b.dataset.sort === sort.key) th.setAttribute("aria-sort", sort.dir > 0 ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    }
    const on = [];
    for (const [slug, a] of dots) {
      const hit = visible.has(slug);
      a.classList.toggle("is-out", !hit);
      a.setAttribute("tabindex", "-1");
      if (hit) on.push(a);
    }
    dotsGroup.append(...on);
    drawCone(pos, radius);
    const n = shown.length;
    $("count").textContent = n === data.length ? `${n} clusters` :
      `${n} of ${data.length} clusters${pos ? ` within ${radius}′` : ""}`;
    $("empty").hidden = n > 0;
    const hint = $("q-hint");
    hint.classList.toggle("is-active", !!pos);
    hint.textContent = pos
      ? `Cone search around RA ${pos.ra.toFixed(4)}°, Dec ${pos.dec.toFixed(4)}° with radius ${radius}′.`
      : "Coordinates (J2000, sexagesimal or decimal degrees) start a cone search with this radius.";
  }

  /* ---- URL state ---- */
  function saveState() {
    const p = new URLSearchParams();
    for (const [k, el] of Object.entries(fields)) {
      if (el.type === "checkbox") { if (el.checked) p.set(k, "1"); }
      else if (el.value.trim() !== "" && !(k === "r" && el.value === "10")) p.set(k, el.value.trim());
    }
    if (!sort.auto) p.set("sort", (sort.dir < 0 ? "-" : "") + sort.key);
    const qs = p.toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  }
  function loadState() {
    const p = new URLSearchParams(location.search);
    for (const [k, el] of Object.entries(fields)) {
      if (!p.has(k)) continue;
      if (el.type === "checkbox") el.checked = p.get(k) === "1";
      else el.value = p.get(k);
    }
    const s = p.get("sort");
    if (s) sort = { key: s.replace(/^-/, ""), dir: s.startsWith("-") ? -1 : 1, auto: false };
  }

  /* ---- events ---- */
  let timer = 0;
  const later = () => { clearTimeout(timer); timer = setTimeout(apply, 120); };
  for (const el of Object.values(fields)) {
    el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input", later);
  }
  $("finder").addEventListener("submit", (e) => { e.preventDefault(); apply(); });
  $("reset").addEventListener("click", () => {
    sort = { key: "name", dir: 1, auto: true };
    setTimeout(apply, 0);
  });
  table.tHead.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-sort]");
    if (!b) return;
    const key = b.dataset.sort;
    sort = { key, dir: sort.key === key ? -sort.dir : 1, auto: false };
    apply();
  });

  /* map tooltip + row/dot linking */
  const frame = dotsGroup.closest(".skymap-frame");
  function showTip(a) {
    const d = data.find((x) => x.s === a.dataset.slug);
    if (!d) return;
    tip.replaceChildren();
    const strong = document.createElement("strong");
    strong.textContent = d.n;
    const span = document.createElement("span");
    span.textContent = `z = ${d.z}, ${d.m} model${d.m === 1 ? "" : "s"}`;
    tip.append(strong, span);
    tip.hidden = false;
    const fr = frame.getBoundingClientRect();
    const dr = a.querySelector(".dot-mark").getBoundingClientRect();
    let x = dr.left + dr.width / 2 - fr.left + 12, y = dr.top - fr.top - 8;
    tip.style.left = "0px"; tip.style.top = "0px";
    const tw = tip.offsetWidth;
    if (x + tw > fr.width - 4) x = dr.left - fr.left - tw - 12;
    tip.style.left = `${Math.max(4, x)}px`;
    tip.style.top = `${Math.max(4, y - tip.offsetHeight / 2)}px`;
  }
  const hideTip = () => { tip.hidden = true; };
  dotsGroup.addEventListener("pointerover", (e) => { const a = e.target.closest(".dot"); if (a) showTip(a); });
  dotsGroup.addEventListener("pointerout", (e) => { if (e.target.closest(".dot")) hideTip(); });
  tbody.addEventListener("pointerover", (e) => {
    const tr = e.target.closest("tr");
    for (const a of dotsGroup.querySelectorAll(".is-hover")) a.classList.remove("is-hover");
    if (tr) { const a = dots.get(tr.dataset.slug); if (a) { a.classList.add("is-hover"); dotsGroup.append(a); } }
  });
  tbody.addEventListener("pointerleave", () => {
    for (const a of dotsGroup.querySelectorAll(".is-hover")) a.classList.remove("is-hover");
  });

  /* CSV of the rows currently shown */
  $("csv").addEventListener("click", () => {
    const cone = shown.some((x) => x.sep !== null);
    const head = ["name", "common_names", "aka", "ra", "dec", "ra_deg", "dec_deg", "z", "n_models",
      "has_public_model", "has_jwst_model", "programs", "lensed_transients", "url"];
    if (cone) head.splice(1, 0, "sep_arcmin");
    const esc = (v) => { const s = String(v ?? ""); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const base = new URL("clusters/", location.href).href;
    const lines = [head.join(",")];
    for (const x of shown) {
      const d = x.d;
      const row = [d.n, d.cn.join("; "), d.aka.join("; "), d.rs, d.ds, d.ra, d.dec, d.z, d.m,
        d.pub ? 1 : 0, d.jw ? 1 : 0, d.p.join("; "), d.t.join("; "), `${base}${d.s}.html`];
      if (cone) row.splice(1, 0, x.sep.toFixed(2));
      lines.push(row.map(esc).join(","));
    }
    const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "clusters.csv";
    document.body.append(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  });

  loadState();
  const filters = $("filters");
  const anyFilter = ["zmin", "zmax", "program", "cat", "pub", "jw", "tr"].some((k) =>
    fields[k].type === "checkbox" ? fields[k].checked : fields[k].value !== "");
  if (anyFilter || window.matchMedia("(min-width: 720px)").matches) filters.open = true;
  apply();
})();
