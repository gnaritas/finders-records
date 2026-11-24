# Post-fix re-sweep t_5e0d4158 2026-11-24 — LIVE origin (fix commit 09de94b, live==local byte-verified)
# Fast path per visual-verify.md: extended DOM gates + dsf2 full-page captures; sheets+vision run separately.
import json, os, time
from playwright.sync_api import sync_playwright

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ORIGIN = "https://finders-records-demo.up.railway.app"
OUT = "/Users/rleon/.hermes/projects/websites/sites/finders-records/shots2"
os.makedirs(OUT, exist_ok=True)

PAGES = ["/", "/shop", "/vinyl-records", "/cds-tapes-dvds", "/contact", "/privacy", "/thanks", "/nonexistent-xyz"]
NAME = {"/": "index", "/shop": "shop", "/vinyl-records": "vinyl", "/cds-tapes-dvds": "cds",
        "/contact": "contact", "/privacy": "privacy", "/thanks": "thanks", "/nonexistent-xyz": "notfound"}

GATE_JS = r"""() => {
  var iw = document.documentElement.clientWidth;
  function desc(e){
    var c = (e.className && e.className.toString) ? e.className.toString().split(' ')[0] : '';
    return e.tagName + (c ? '.' + c : '') + '@' + Math.round(e.getBoundingClientRect().right);
  }
  var els = [].slice.call(document.querySelectorAll('body *')).filter(function(e){
    var r = e.getBoundingClientRect();
    return r.right > window.innerWidth + 1 && r.width > 0 && !e.closest('iframe');
  });
  var small = [].slice.call(document.querySelectorAll('body *')).filter(function(e){
    return e.children.length === 0 && e.textContent.trim().length > 0 &&
           parseFloat(getComputedStyle(e).fontSize) < 11.4 &&
           e.offsetParent !== null;
  });
  var bad = [].slice.call(document.querySelectorAll('img')).filter(function(i){return !i.complete || i.naturalWidth === 0;});
  // main top-level block junctions for gap analysis
  var main = document.querySelector('main') || document.body;
  var blocks = [].slice.call(main.children).map(function(e){
    var r = e.getBoundingClientRect();
    return {tag: e.tagName + (e.className && e.className.toString ? '.' + e.className.toString().split(' ')[0] : ''),
            top: Math.round(r.top + window.scrollY), bottom: Math.round(r.bottom + window.scrollY), h: Math.round(r.height)};
  });
  // tag/status column edges (cds alignment claim)
  var tags = [].slice.call(document.querySelectorAll('.tagc, .pill, td, th')).map(function(e){
    var r = e.getBoundingClientRect();
    return {t: e.textContent.trim().slice(0, 18), l: Math.round(r.left), rgt: Math.round(r.right), top: Math.round(r.top + window.scrollY), sz: getComputedStyle(e).fontSize};
  });
  // iframe containers
  var frames = [].slice.call(document.querySelectorAll('iframe')).map(function(f){
    var r = f.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height), right: Math.round(r.right), title: f.getAttribute('title') || ''};
  });
  var nav = document.querySelector('nav');
  return {
    iw: iw, sw: document.documentElement.scrollWidth,
    overflow: els.slice(0, 8).map(desc),
    smallN: small.length,
    smallSample: small.slice(0, 6).map(function(e){ return desc(e) + ' ' + getComputedStyle(e).fontSize + ' "' + e.textContent.trim().slice(0, 26) + '"'; }),
    broken: bad.length,
    blocks: blocks, tags: tags.slice(0, 40), frames: frames,
    navTrunc: nav ? (nav.scrollWidth > nav.clientWidth + 2) : null,
    textLen: (document.body.innerText || '').trim().length
  };
}"""

metrics = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox"])
    for vp, w, h, mob in (("desktop", 1280, 900, False), ("mobile", 390, 844, True)):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=mob)
        pg = ctx.new_page()
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        for path in PAGES:
            name = NAME[path]
            try:
                resp = pg.goto(ORIGIN + path, wait_until="networkidle", timeout=45000)
                status = resp.status if resp else 0
            except Exception as e:
                status = -1
                print("GOTO FAIL", path, vp, str(e)[:120])
            pg.wait_for_timeout(800)
            g = pg.evaluate(GATE_JS)
            g["status"] = status
            metrics[(vp + "-" + name)] = g
            pg.screenshot(path=f"{OUT}/{name}_{vp}.png", full_page=True)
        # contact map real-tiles capture: scroll to iframe, dwell, viewport-only shot
        pg.goto(ORIGIN + "/contact", wait_until="networkidle", timeout=45000)
        pg.evaluate("() => { var f = document.querySelector('iframe'); if (f) f.scrollIntoView({block:'center', behavior:'instant'}); }")
        time.sleep(9)
        maprect = pg.evaluate("() => { var f = document.querySelector('iframe'); if (!f) return null; var r = f.getBoundingClientRect(); return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),h:Math.round(r.height)}; }")
        pg.screenshot(path=f"{OUT}/map_{vp}_view.png")  # viewport-only, no full_page
        metrics["map-" + vp] = {"rect": maprect}
        if vp == "desktop":
            metrics["console-desktop"] = errors[:8]
        ctx.close()
    b.close()

# ---- verdicts (Python side) ----
def blocks_defects(ms):
    out = []
    hs = [b["h"] for b in ms["blocks"] if b["h"] > 2]
    if len(hs) >= 4:
        hs2 = sorted(hs); med = hs2[len(hs2)//2]
        bl = ms["blocks"]
        for a, bb in zip(bl, bl[1:]):
            gap = bb["top"] - a["bottom"]
            if gap < -2:
                out.append(f"OVERLAP {a['tag']}x{bb['tag']} {gap}px")
            elif med > 30 and gap > med * 2.6:
                out.append(f"GAP {a['tag']}->{bb['tag']} {gap}px (median {med}px)")
    return out

def cds_defects(m):
    out = []
    if m["smallN"] == 0:
        out.append("CDSCHECK smallN=0")  # placeholder marker, fine
    return out

defects = []
for k, m in metrics.items():
    if k.startswith("map-") or k.startswith("console"):
        continue
    bad = []
    if m.get("status") != 200: bad.append(f"http={m.get('status')}")
    if m.get("overflow"): bad.append("overflow:" + ",".join(m["overflow"]))
    if m.get("smallN"): bad.append(f"small-text n={m['smallN']} " + " | ".join(m.get("smallSample", [])[:3]))
    if m.get("broken"): bad.append(f"broken-img={m['broken']}")
    if m.get("navTrunc"): bad.append("nav-trunc")
    if m["textLen"] < 60: bad.append("empty-text")
    bad += blocks_defects(m)
    for fr in m.get("frames", []):
        if fr["w"] < 200: bad.append(f"iframe-too-narrow w={fr['w']}")
    tag = "DEFECT " if bad else "ok "
    defects += [(k, b) for b in bad]
    print(tag + k + ": " + ("; ".join(bad) if bad else f"pages fine, text={m['textLen']}w frames={m['frames']}"))

mr = metrics.get("map-desktop", {}).get("rect")
print("MAP containers:", metrics.get("map-desktop", {}).get("rect"), metrics.get("map-mobile", {}).get("rect"))
print("console errors (desktop):", metrics.get("console-desktop"))
json.dump(metrics, open(OUT + "/metrics2.json", "w"), indent=1)
print("DEFECTS_TOTAL", len(defects))
