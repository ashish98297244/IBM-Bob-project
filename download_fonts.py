"""Download TikZJax fonts locally so the app works without internet."""
import urllib.request
import os
import re

css = open("static/tikzjax-fonts.css", encoding="utf-8").read()

# Extract font filenames: url('../bakoma/ttf/cmb10.ttf')
fonts = re.findall(r"url\(['\"]?\.\./([^'\")\s]+)['\"]?\)", css)
print(f"Total fonts found: {len(fonts)}")

os.makedirs("static/bakoma/ttf", exist_ok=True)
base = "https://tikzjax.com/"
ok = 0
fail = 0
for f in fonts:
    dest = os.path.join("static", f.replace("/", os.sep))
    if os.path.exists(dest):
        ok += 1
        continue
    try:
        urllib.request.urlretrieve(base + f, dest)
        ok += 1
        print(f"  OK: {f}")
    except Exception as e:
        fail += 1
        print(f"  FAIL: {f} — {e}")

print(f"\nDone. Downloaded: {ok}, Failed: {fail}")
