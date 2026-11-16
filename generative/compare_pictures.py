"""One picture of the parts side by side, hand-drawn above and generative below.

    sh:  for each part, cad stl snapshot baselines/<part>.stl out/pic_v1_<part>.png --camera iso
                        cad stl snapshot out/<part>.stl       out/pic_v2_<part>.png --camera iso
    python generative/compare_pictures.py     ->  media/parts_v1_v2.png

Needs matplotlib.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
PARTS = [("thigh", "Thigh"), ("tray", "Chassis tray"), ("shank", "Lower leg (not adopted)")]

fig, axes = plt.subplots(2, len(PARTS), figsize=(6 * len(PARTS), 9), facecolor="white")
for column, (part, title) in enumerate(PARTS):
    report = json.load(open(os.path.join(OUT, f"{part}_eval.json")))
    for row, (version, key, label) in enumerate((("v1", "baseline", "hand-drawn"), ("v2", "generative", "generative"))):
        ax = axes[row][column]
        ax.imshow(plt.imread(os.path.join(OUT, f"pic_{version}_{part}.png")))
        ax.axis("off")
        ax.set_title(f"{title}: {label}, {report[key]['mass_g']:.2f} g", fontsize=15)
fig.tight_layout()
os.makedirs(os.path.join(HERE, "media"), exist_ok=True)
fig.savefig(os.path.join(HERE, "media", "parts_v1_v2.png"), dpi=110)
print("wrote media/parts_v1_v2.png")
