# Divya Kahaniyan — Devotional artwork library

The video renderer checks this library before using its built-in procedural backgrounds.

## Folders

- `krishna/` — Krishna and Vishnu artwork (selected for explicit Ekadashi/Vishnu observances)
- `shiva/` — Shiva and Mahadev artwork
- `hanuman/` — Hanuman and Bajrangbali artwork
- `lakshmi/` — Lakshmi, Diwali and Dhanteras artwork
- `ganesha/` — Ganesha and Vinayak artwork
- `surya/` — Surya Dev, Chhath and Sankranti artwork
- `purnima/` — moonlit and full-moon artwork
- `festival/` — general festival artwork
- `general/` — neutral Panchang, temple and devotional atmosphere artwork

## Image requirements

Add JPG, JPEG, PNG or WebP files to the appropriate folder. Portrait 9:16 images (ideally 1080 × 1920) work best. Keep the central devotional subject clear and leave some visual breathing room near the top and bottom for captions.

**Use clean artwork only:** do not bake in dates, Panchang timings, Hindi captions, logos, watermarks or banners. The renderer adds the Divya Kahaniyan branding and subtitles itself.

## Selection behaviour

- Explicit festival names take priority, followed by Ekadashi and Purnima tithi cues.
- Weekday alone is not treated as proof of a religious observance.
- A matching theme image is selected deterministically by date and scene, so scenes can vary when multiple images exist.
- If a theme folder has no images, the renderer tries `general/`.
- If both folders are empty, the existing built-in visual renderer remains as a safe fallback.

No image-generation API, paid service or additional runtime dependency is required.
