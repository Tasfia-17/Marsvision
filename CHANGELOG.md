# MarsVision Changelog

## [Sprint — Apr 22 2026] Award Submission Push

### AI Vision Pipeline (Seedream 5.0 + Seedance 2.0)

**`hermes_rover/perception.py` — complete rewrite**
- Rich terrain prompt library: 8 terrain types (crater rim, flat plains, rocky field, sand dunes, bedrock, hazard, return base, default)
- Sol lighting system: dawn / morning / midday / afternoon / dusk based on mission time
- Mars weather states: clear, dusty, storm, dust devil, frosty CO₂
- Camera simulation: mastcam, navcam, hazcam_front, hazcam_rear with realistic lens descriptions
- `generate_terrain_image()` — async Seedream 5.0 call, 1920×1080, b64 response, auto-fallback to 2048×2048
- `generate_terrain_gallery()` — parallel multi-camera gallery generation

**`hermes_rover/tools/scene_video_tool.py` — major upgrade**
- API key pool (4 keys) with round-robin rotation for high-volume generation
- Mission phase detection: explore / hazard / return / sample / storm / survey
- Cinematic motion prompt library per phase (dolly, orbital arc, handheld shaky, etc.)
- I2V pipeline: captures real Gazebo frame → falls back to Seedream 5.0 → animates with Seedance 2.0
- T2V fallback when no image available
- `generate_mission_gallery_videos()` — parallel multi-scene video generation
- 1080p output, watermark disabled, 5s duration

### Media Generation & Assets

**`generate_media.py` — new batch generation script**
- Generates 8 curated terrain images + 4 cinematic videos in one run
- Skips already-generated files (idempotent)
- Writes `docs/generated_media/manifest.json` with sizes and timestamps

**`docs/generated_media/images/` — 8 terrain images committed**
| File | Scene |
|---|---|
| `jezero_crater_dawn.jpg` | Jezero Crater floor, blue-pink pre-dawn twilight |
| `rocky_field_midday.jpg` | Dense basalt boulder field, harsh midday sol |
| `crater_rim_golden_hour.jpg` | Crater rim edge, golden hour long shadows |
| `dust_storm_approaching.jpg` | Global dust storm wall on horizon |
| `bedrock_scientific_target.jpg` | Noachian mudstone outcrop, drill target |
| `sand_dunes_afternoon.jpg` | Dark basaltic barchan dunes, afternoon sol |
| `lander_return_path.jpg` | Wheel tracks leading back to lander |
| `olympus_mons_vista.jpg` | Olympus Mons panoramic vista |

### Dashboard (Next.js)

**`dashboard/components/MediaGallery.tsx` — new component**
- Tabbed Images / Videos view
- Live gallery fetch from API (`/terrain/gallery`, `/video/gallery`)
- Inline scene-context input + ⚡ Generate button triggers API generation
- Image grid (3-col, aspect-video) with hover metadata overlay
- Video grid (2-col) with native `<video>` player

**`dashboard/app/page.tsx`** — MediaGallery panel added to main layout

**`dashboard/lib/api.ts`** — added `getTerrainGallery`, `getVideoGallery`, `generateGallery`

### API (`api/main.py`)

New endpoints added:
- `POST /video/generate` — generate single Seedance 2.0 video
- `POST /video/gallery` — generate multiple videos in parallel
- `POST /terrain/generate` — generate single Seedream 5.0 terrain image
- `POST /terrain/gallery` — generate multi-camera terrain gallery
- `GET  /terrain/gallery/{filename}` — serve terrain image file
- `GET  /video/gallery/{filename}` — serve video file
- `GET  /terrain/gallery` — list all generated terrain images
- `GET  /video/gallery` — list all generated videos

### Notes
- Videos pending: BytePlus Seedance 2.0 video API requires paid account credits
- All image generation tested and working (8 images, ~650–800KB each at 1920×1080)
