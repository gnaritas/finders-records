# Montage sheets + OpenRouter gemini-flash battery — post-fix re-sweep t_5e0d4158, 2026-11-24
# Budget: 4 vision calls (3 sheets + map crop). Claims must survive measurement to count.
import base64, io, json, os, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

OUT = "/Users/rleon/.hermes/projects/websites/sites/finders-records/shots2"

def scaled(name, w):
    im = Image.open(os.path.join(OUT, name)).convert("RGB")
    h = int(im.height * w / im.width)
    return im.resize((w, h), Image.LANCZOS)

def sheet(name, tiles, w):
    ims = [scaled(t, w) for t in tiles]
    mh = max(i.height for i in ims)
    sh = Image.new("RGB", (w * len(ims), mh), (255, 255, 255))
    x = 0
    for i in ims:
        sh.paste(i, (x, 0)); x += w
    sh.save(os.path.join(OUT, name), quality=82)
    return sh.size

def sheet_grid(name, rows, w):
    pieces = [[scaled(t, w) for t in row] for row in rows]
    row_h = [max(i.height for i in r) for r in pieces]
    sh = Image.new("RGB", (w * max(len(r) for r in rows), sum(row_h)), (255, 255, 255))
    y = 0
    for r, rh in zip(pieces, row_h):
        x = 0
        for i in r:
            sh.paste(i, (x, y)); x += w
        y += rh
    sh.save(os.path.join(OUT, name), quality=82)
    return sh.size

# map native-res crop: iframe rect x=124 y=240 w=1032 h=420 at dsf2 => 248,480,2064,840
mi = Image.open(os.path.join(OUT, "map_desktop_view.png")).convert("RGB")
mc = mi.crop((248, 480, 248 + 2064, 480 + 840)).resize((1200, int(840 * 1200 / 2064)), Image.LANCZOS)
mc.save(os.path.join(OUT, "map_crop.jpg"), quality=85)

sizeA = sheet("re-sheet-desktop-1.jpg", ["index_desktop.png", "shop_desktop.png", "vinyl_desktop.png"], 640)
sizeB = sheet_grid("re-sheet-desktop-2.jpg", [["contact_desktop.png", "cds_desktop.png"], ["privacy_desktop.png", "notfound_desktop.png"]], 760)
sizeC = sheet_grid("re-sheet-mobile.jpg", [["index_mobile.png", "shop_mobile.png"], ["contact_mobile.png", "cds_mobile.png"]], 420)
print("sheets:", sizeA, sizeB, sizeC, mc.size)

KEY = None
for line in open(os.path.expanduser("~/.hermes/.env")):
    if line.startswith("OPENROUTER_API_KEY="):
        KEY = line.split("=", 1)[1].strip()
assert KEY, "no OPENROUTER key"

GUARD = ("GUARDS — do NOT flag: faint background decorations or rings behind text; intentional dashed/decorative short rules; "
         "ordinary responsive line-wrapping in footers or lists; 1-2px alignment nits; scrollbar-gutter right edge; "
         "blank/grey map tiles INSIDE a map frame (adjudicated separately); even side-by-side placement of different pages in this montage (it is a contact sheet, not one page). "
         "End your answer with exactly one line: VERDICT: CLEAN  or  VERDICT: DEFECTS: <itemized list with page+section names>")

QUESTIONS = {
  "re-sheet-desktop-1.jpg": "These are three full-page DESKTOP (1280px wide) screenshots side by side of a vinyl record store website: page 1 Home, page 2 The Shop, page 3 Vinyl. "
      "List every visual or layout defect: misaligned columns/grids, text overflowing or clipped, uneven margins/spacing, overlapping elements, stretched or cropped images, broken nav or footer, inconsistent widths, garbled characters. " + GUARD,
  "re-sheet-desktop-2.jpg": "These are four full-page DESKTOP (1280px wide) screenshots in a 2x2 montage of a record store website: top-left Visit/Contact page (contains a Google map frame), top-right CDs & Tapes page, bottom-left Privacy page, bottom-right 404 page. "
      "List every visual or layout defect: misaligned columns/grids, text clipped, uneven spacing or huge empty gaps between sections, overlapping elements, broken nav/footer, garbled characters. Name the page and section for each. " + GUARD,
  "re-sheet-mobile.jpg": "These are four full-page MOBILE (390px wide) screenshots in a 2x2 montage of a record store website: top-left Home, top-right The Shop, bottom-left Visit/Contact, bottom-right CDs & Tapes. "
      "List every visual or layout defect at this width: text overflowing or clipped horizontally, elements wider than the screen, broken/hamburger nav, overlapping elements, unreadably small text, stretched images. Name the page and section for each. " + GUARD,
  "map_crop.jpg": "This is a zoomed capture of a Google Maps embed frame near a street address on a business website's contact page. Does it show a rendered street map (streets, blocks, labels) with a red location marker/pin, or is it blank/grey? Describe exactly what is visible inside the frame. End with exactly one line: VERDICT: MAP-RENDERED or VERDICT: MAP-BLANK",
}

def call(fname_prompt):
    fname, prompt = fname_prompt
    b = base64.b64encode(open(os.path.join(OUT, fname), "rb").read()).decode()
    body = json.dumps({
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}}]}],
        "max_tokens": 700,
    }).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read())
            return fname, j["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == 2:
                return fname, "ERROR: " + str(e)[:200]

results = {}
with ThreadPoolExecutor(max_workers=4) as ex:
    for fname, ans in ex.map(call, QUESTIONS.items()):
        results[fname] = ans

out = {}
for fname, ans in results.items():
    verdict = [l for l in (ans or "").splitlines() if l.strip().startswith("VERDICT:")]
    out[fname] = {"answer": ans, "verdict": verdict[-1].strip() if verdict else "NO-VERDICT-LINE"}
    print("=== " + fname + " ===")
    print((ans or "(none)")[:1200])
    print()
json.dump(out, open(os.path.join(OUT, "vision-results2.json"), "w"), indent=1)
print("saved vision-results2.json")
