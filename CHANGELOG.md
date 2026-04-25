# MarsVision Changelog

## [Sprint — Apr 25 2026] Data Pipeline Upgrade

### Seedance 2.0 Multi-Reference I2V (`hermes_rover/tools/scene_video_tool.py`)

**Before:** Single Seedream 5.0 frame → Seedance 2.0 I2V (1 reference image)

**After:** 3 simultaneous camera angles (mastcam + navcam + hazcam_front) generated in parallel via Seedream 5.0, all fed as `[Image1]`, `[Image2]`, `[Image3]` to Seedance 2.0 multi-reference I2V in a single request.

- `_capture_multi_reference()` — parallel async capture from all 3 cameras
- `_create_multi_ref_i2v_task()` — builds multi-reference content payload with annotated reference tags
- `execute()` — tries multi-ref (≥2 frames) → single-ref → T2V fallback chain
- Mode field now reports `multi_ref_i2v_3frames` / `i2v_seedream` / `t2v`
- `reference_frames` count included in response

Why it matters: Seedance 2.0 supports up to 9 images + 3 videos + 3 audio per request. Using 3 simultaneous camera angles gives the model spatial context — it sees the terrain from wide (navcam), telephoto (mastcam), and close obstacle (hazcam) perspectives simultaneously, producing more consistent and grounded video than single-frame I2V.

### RLDS-Compatible Training Data Export (`hermes_rover/tools/training_data_tool.py`)

Complete rewrite. Now mirrors the NVIDIA DreamGen 4-stage pipeline:

**Stage 1** — Parse mission trace into raw observations  
**Stage 2** — Pseudo-action extraction via finite-difference inverse dynamics  
**Stage 3** — Annotate with language instructions and reward signals  
**Stage 4** — Export as RLDS-compatible JSON

New features:
- `_extract_action_vector()` — 6-DOF continuous action vector `[dx, dy, dz, d_roll, d_pitch, d_yaw]` inferred from consecutive observation pairs
- `_compute_reward()` — shaped reward: +1.0 success, -1.0 safety halt, +0.3 video generated, +0.1 nav step, -0.2 hazard proximity, -0.3 dangerous tilt
- `_build_state_vector()` — compact 7D state `[x, y, heading, tilt, lidar, battery, distance]`
- RLDS standard fields: `language_instruction`, `steps[].observation`, `steps[].action`, `steps[].reward`, `steps[].is_terminal`
- Dataset index tracks aggregate stats: success/failure/partial counts, total distance, total steps
- Compatible with: BC, DAgger, IQL, ACT, RT-2, OpenVLA

### Multi-Reference Video Generation (`generate_media.py`)

- `create_multi_ref_video_task()` — new function, sends existing terrain images as multi-reference to Seedance 2.0
- `VIDEO_REF_MAP` — maps each video scene to its most relevant terrain images (e.g. crater rim video uses `crater_rim_golden_hour.jpg` + `jezero_crater_dawn.jpg` + `olympus_mons_vista.jpg`)
- `generate_video()` — now accepts `ref_images` list, uses multi-ref I2V when available
- `main()` — collects all generated terrain images, passes relevant subset to each video

### Self-Running Demo (`demo.py`)

New file. Judges can run `python demo.py` with zero config to see the full pipeline:
- Prints live telemetry
- Runs autonomous mission with colored real-time trace
- Shows mission summary with outcome, distance, video mode, dataset path
- Saves `demo_output.json` with full trace summary

---

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
