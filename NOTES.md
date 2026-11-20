# «Извлечение подписи» (Signature Extractor) v1.0 — stages 1–2 rewritten (+ stage 3 integration)

Basis: «Давай просто заменим весь этап 1 и этап 2, так как код не твой и может сильно расходиться с макетом» ("Let's just replace all of stage 1 and stage 2, since the code isn't yours and may differ a lot from the mockup").
Work only locally on the box: no commits, branches, PRs or cloud agents. Mockups, the i18n table and the icon were not changed.

## How to run

```bash
cd signature-extractor
python -m venv .venv && .venv\Scripts\activate      # Windows (Linux: source .venv/bin/activate)
pip install -r requirements.txt
python main.py [file ...]                            # files from the arguments open right away
python main.py --installer-language en               # only on the first start without settings.json
python -m pytest -q tests                            # 151 tests
```

Screenshots (Linux, Xvfb): `tools/shoot.py <scenario> <light|dark> <ru|en> out.png [W H]`, in batch `tools/runall.sh`,
comparisons `tools/cmpall.py` → `compare/<variant>_<screen>.png` (left the app, right the mockup without the 32 px window title bar).
Needs Tk with Xft fonts (conda-forge `tk` is used; Tk from python-build-standalone draws without Inter and Cyrillic).

## Architecture

- `core/` — no UI imports: `processing.py` (input, loading, processing, crop frame, eraser, ink colour), `export.py` (stage 3; frame margin, SVG and DXF changed per the 2026-11-17 remarks), `centerline.py` (skeleton for DXF), `settings.py`, `i18n.py`, `history.py`, `worker.py`.
- `ui/widgets/` — shared Win11 control engine on Canvas: `base.py` (Box/Control/Tooltip, logical geometry, scale), `controls.py` (Button, ToolButton, IconButton, Link, Toggle, Radio, CheckRow, ComboBox, TextBox with «×»/«✓», Slider, Segmented), `overlay.py` (Popup, MenuPopup, ListPopup, tooltips), `scroll.py` (ScrollArea + thin bar).
- `ui/pages/` — one module per screen: `import_page.py` (1), `process_page.py` + `preview.py` (2), `export_page.py` (3), `settings_page.py` (27, 64–67).
- `ui/dialogs/` — `content.py` (ContentDialog 04, 20, 29, 30, 31, 34, 43), `about.py` (28), `child.py` (modal child window), `color_dialog.py` (10), `formats_help.py` (21 and the help placeholder).
- `ui/app.py` — shell: stepper header, ⋯ menu, navigation, hotkeys, DnD, clipboard, theme/language, background tasks; `ui/platform_win.py` — PMv2 DPI, AppUserModelID, DWM title bar colours, system theme.

## Status by specification item

### Stage 1
| Item | Status |
|---|---|
| Window: app.ico icon, localized title without version, 1280 × 800 (client 1280 × 768), minimum 1024 × 680 | done; Win11 title bar colours via DWM — check on Windows |
| Light/dark/system theme, switching without restart (system polled every 1.5 s) | done, checked 01, 02, 19, 27, 64–67 in both themes |
| RU/EN from the table, «Import», drop zone title | done, EN comparisons taken |
| Quick Share drop zone: r16 card, 4/4 dashes with a 12 inset, r8; 02 while dragging | done |
| ⋯ menu — 5 items in the order of 19, right edge flush with the cards | done |
| Settings as a page in the same window, group order, density 63/7/56, headers 14/600 | done |
| Expandable «Тема» (64) and «Форматы по умолчанию» (65), 20 px radios/checkboxes | done |
| Lists over the field, the selected item in place of the field, accent bar (67, 58) | done (min width 236, max height 392, thin bar) |
| TextBox «Поле рамки»/«Шаблон имени»: «×» inside, «✓» next to it, Enter, tooltips «Применить»/«Очистить» (66); frame margin — numbers only | done |
| «Вкл.»/«Откл.» toggles 14 px in 12 px | done |
| Antialiasing 100/125/150 %, per-monitor DPI v2 | done (PIL supersampling); 125/150 % — check on Windows |
| Scrolling: wheel, thumb, click on the track; thin bar, wider on hover | done |
| GNU GPLv3 — web link | done (both in 27 and in 28) |
| settings.json in %APPDATA%\Signature Extractor, atomic write | done (core/settings.py, tests) |
| `--installer-language` — the only source of the installer language | done |
| Ctrl+O, Esc | done |

### Stage 2
| Item | Status |
|---|---|
| JPG, PNG, BMP, TIFF, WebP, HEIC; others → 04 (together with photos) or 29 (only non-photos/broken file) | done; 04 is shown over screen 1 before processing, «Понятно» continues |
| > 50 MB → red panel 45 without a close cross, no navigation | done |
| Drag and drop of a photo/folder, «Открыть файл», paste from the clipboard; a non-image on the clipboard → clear error | done (strings `errors.clipboard.*` in the table) |
| 03: only the spinner and captions, stepper on «Обработка» | done |
| 62: «Авто» with a found colour — no «Пипетка», line «найден автоматически» and a round swatch | done |
| Colour not separable from text — grey line + pipette | done |
| Auto/manual frame, «Сбросить к авто», eraser, Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z | done |
| Ctrl+S → export if the result is ready | done |
| Before/After, three backgrounds, fine tuning «±0» (05–09) | done |
| AI by default from settings; without DirectX 12/on failure — the regular algorithm | done (core.ai missing → fallback without error); DirectML — check on Windows |
| 20, 29, 30, 57 per the table and mockups | done |

### Stage 3 (moved to the new engine)
| Item | Status |
|---|---|
| Size ComboBox (order, over the field, «Свой размер…» → width/height with «✓», «Сохранить как шаблон» → 34) | done (11, 12, 33, 34, 35, 58) |
| 15 × 5 mm by default, fitting with «Поле рамки» (default 0.5 mm), box outline | done (remark 7) |
| 48: grey line about 300 DPI | done |
| Colours: 5 built-in, «+» → window 10, own colours are saved, deletion via the right-click menu 61, tooltips 60 | done |
| PNG expands (150/300/600, «Поле рамки» as a number + «✓»), SVG/DXF without a chevron, tabs only for enabled formats | done (59) |
| SVG (potracer, outline at the 50 % threshold, no thickening); DXF R2010 — centreline of the given width (0.18 mm) | changed per remarks 8–9 |
| One save dialog, base name, 43, 31, line 13, «Готово» → clean 55 | done; checked with real writes (PNG/SVG/DXF, «Сохранить с номером») |
| Formats help (21) — child window | done |

## Tests
`python -m pytest -q tests` → **151 passed** (after the fourth batch of remarks 2026-11-17: +13 in `tests/test_remarks3.py`, +11 in `tests/test_remarks4.py`; below is the original set of 81): 65 earlier ones (export, i18n, settings, worker) + 16 new `tests/test_processing.py` (scan_inputs, extensions, DPI, broken file, downscaling large photos, signature detection and ruled-line removal, ink colour states found/same/off/manual, own frame and clamp, eraser, empty photo, RGBA, thickness, undo history).

## Comparisons
`compare/` — 123 images: 41 states × (RU light, RU dark, EN light):
01, 02, 03, 04, 19, 20, 27 (whole page 1576 px), 27b (scrolled), 28, 29, 30, 45, 64–67, 05–09, 53, 55, 57, 62, 10, 11, 12, 13, 21, 31, 33, 34, 35, 43, 48, 54, 58–61.
Best to look at: `light_05`, `light_59`, `dark_27`, `en_light_59`, `light_58`, `light_10`.

## Deviations from the mockups and why
1. **Font**: Inter on Linux instead of Segoe UI Variable; Tk accepts only whole px, so 12.5 → 13 and 13.5 → 14. Hence the difference in text width and occasional different line breaks (21). On Windows Segoe UI Variable is used.
2. **Window title bar**: the screenshots (Xvfb without a window manager) have no system title bar, so it is cropped from the mockup too; child windows 10 and 21 also have no title bar under Xvfb.
3. **Tooltips**: light native Win11 tooltips, while in mockups 57 and 60 they are dark (per the decision "native Win11 matters more").
4. **Export preview**: file = box size (stage 3 decision), so the signature fills the box, and the dimension lines and badge show the file size (354 × 118 px · 15.0 mm). The mockup shows the content size (246 × 94 px · 10.4 mm).
5. **«Свой размер» fields**: 64 px, digits only, with «✓»/«×» (stage 3 decision). In mockup 12 the field is 88 px with the text «20 мм» and no «✓».
6. **06/07/09**: in the mockups the ink colour card body is hidden when the filter is on, but per the specification it is visible — done per the specification. On 05 the mockup is in manual mode, while the app defaults to «Авто» (the 05 screenshot has manual mode on, as in the mockup).
7. **Different test photo**, so the auto frame, stroke count and sizes in mm differ from the mockup because of the data, not the layout.
8. **Theme in the dark-theme screenshots**: the harness sets «Тёмная» explicitly, while mockup 27 has «Использовать параметры системы» selected.
9. **List 35**: the list is at least 236 wide (approved), while the mockup has 184.
10. **Engine**: controls are drawn on Canvas (PIL, supersampling), not with standard CTk widgets. Reason: exact Win11 radii, outlines and states, which CTk does not provide.
11. **«Размеры подписи» in Settings** — for now only the choice of the default size; the full manager (36/37) is stage 5.
12. **Help**: outside formats (start/prep/process/batch) the window is assembled from the `help.<topic>.*` strings as a placeholder; the full help centre 22–26 is stage 5.
13. **Numbering** for «Сохранить с номером» — «имя (2)», as in the stage 3 core.

## Added i18n strings
Approved 2026-11-17 and added to the main table: the project's `i18n/strings_ru_en.csv` and `/workspace/prompt/v2/i18n/strings_ru_en.csv` + `.xlsx` (the files are identical, the Excel table range «Strings» extended to A1:E299). The strings follow `errors.retry`; the separate `strings_added.csv` and its loader were removed.
| id | RU | EN |
|---|---|---|
| `errors.clipboard.title` | Не удалось вставить изображение | Can't paste the image |
| `errors.clipboard.body` | В буфере обмена нет изображения | There's no image on the clipboard |

## Decisions (approved 2026-11-17)
1. Ctrl+V without an image on the clipboard shows the error `errors.clipboard.title` / `errors.clipboard.body`; the strings were added to the main table.
2. The export preview in box modes shows the file size (= box), as now.
3. The «Свой размер» fields stay as now: 64 px, digits only, «✓»/«×».
4. Tooltips — native light Win11.
5. Duplicate numbering — «имя (2)».
6. «О программе» — dialog 28.

## Check on Windows only
- Per-monitor DPI v2 at 100/125/150 % and moving the window between monitors; Segoe UI Variable sharpness.
- DWM title bar colours (attributes 20/35/36) in both themes; the icon in the title bar and taskbar (AppUserModelID).
- Position of child windows 10/21 with the system title bar (the whole window is centred); modality and flashing on a click on the main window.
- System theme from the registry (AppsUseLightTheme) and switching on the fly.
- Drag and drop from File Explorer (tkinterdnd2), pasting an image and files from the clipboard.
- The save dialog with `confirmoverwrite=False` and the following 43.
- AI/DirectML (onnxruntime-directml), fallback without DirectX 12.
- HEIC via pillow-heif.

## Changes per remarks (2026-11-17, command «Вносим изменения»)
Backup of the tree before the edits: `/workspace/rewrite/_backup_before_remarks_2026-11-17`. Screenshots: `/workspace/rewrite/remarks_shots`
(`tools/shoot_remarks.sh`, scenarios `r_*` in `tools/scenarios.py`; export comparison — `tools/render_export.py`).

1. **Theme — no value in the header**: the selected value on the right of the «Тема» card was removed, only the chevron is left (as in Calculator).
2. **Order of options**: «Светлая», «Тёмная», «Использовать параметры системы» (`THEME_ORDER` in `settings_page.py`).
3. **Theme icon**: Fluent «Color» (palette, E790 in Calculator), `ic_fluent_color_20_regular` from fluentui-system-icons (MIT), 1 px; `assets/icons/theme.png`, source `svgs/fluent_color_20_regular.svg`.
4. **«Лицензия» in «Сведения»**: cause — the label was drawn on the card canvas from outside, and the card erases and redraws its canvas on hover. Now the page passes such elements via `SCard.extra_draw`, and they are redrawn with the card. The dividers in the expanded «Форматы по умолчанию» card had the same bug, fixed the same way.
5–6. **Screen 2, tools**: by default no tool is pressed. Pressing the active tool again turns it off. A left click outside the preview and outside the toolbar also turns the tool off. The crop frame is always visible; handles and editing exist only with «Рамка области». Without a tool and with the eraser the frame is shown dashed without handles, for viewing only.
7. **«Поле рамки» in all modes**: 0.5 mm by default (`DEFAULT_MARGIN_MM`). In box, own-size and template modes the file equals the box, and the signature is fitted into the box minus the margin. A margin that does not fit the box is not accepted (e.g. in 15 × 5 the margin must be under 2.5 mm). Why it "did not work" before in «Как в исходнике» mode: the file size changed, but the preview fitted the whole file and did not draw its border, so the margin was invisible. Now the dashed file border is drawn in all modes. Settings migration: in v1 the value 2.0 was the default, so on the first start it is replaced with 0.5 (`settings_version` = 2).
8. **SVG without thickening**: `MIN_STROKE_MM = 0`, the outline is built at the 50 % threshold, stroke thickness as in the source. The `thicken_thin_strokes` function remains, but export does not call it.
9. **DXF — centreline**: in `core/centerline.py` the skeleton is built like this:
   - Zhang–Suen thinning;
   - a graph of end points and junctions;
   - short spurs are pruned (length under ≈1.2 stroke widths);
   - at each junction the two straightest branches are continued, so an «X» gives two strokes;
   - the line is smoothed and simplified.
   The DXF gets open LWPOLYLINEs with `const_width` = the thickness and the nearest standard `lineweight`; `$LWDISPLAY` = 1; no HATCH. Line ends are extended by half the thickness to cover the joints. The «Толщина линии» field is in the DXF card, which expands with a chevron like the PNG card. The field accepts only numbers from 0.01 to 5 mm (two decimals), with «×» and «✓», 0.18 mm by default. The value is saved in `settings.json` as `dxf_line_mm`. New i18n strings: `export.dxf.line`, `export.dxf.line.desc`, the Excel table now goes to A1:E301. The DXF tab preview draws the centreline in the chosen thickness.
10. **Export preview**: instead of a 0.62 × 0.52 share, the frame is fitted into the whole area minus the space for the badge, caption and dimension lines (`preview_fit`).

Tests: 121, were 81. New checks:
- margin in all modes, the PNG transparent band equals the margin, `margin_fits`;
- SVG without thickening, outline thickness matches the source;
- centreline: middle of a band, ring, spur pruning, cross;
- DXF: only LWPOLYLINE, width and `lineweight`, `$LWDISPLAY`, thickness limit;
- settings: new defaults, migration 2.0 → 0.5, `dxf_line_mm` validation;
- screen 2 tools (`tests/test_tools.py`).

## Changes per remarks 11–19 (2026-11-17, second batch, «Вносим изменения»)
Backup of the tree before the edits: `_backup_before_remarks2_2026-11-17/` (and the earlier archive `_backup_before_remarks2_2026-11-17.rewrite_code.zip`).

- **11. DXF, centreline without false bridges** (`core/centerline.py`):
  - `stitch_edges`: joins halves of a stroke where the skeleton walk stopped with an "empty" end; a remaining loose end next to a junction is attached to it. Tails with an empty end and tiny loops inside a junction are removed together with spurs.
  - `resolve_bridges`: a short edge between two junctions (up to 8 × stroke width). If both strokes enter and leave along it (within 60°), it is a shallow crossing or merge: the strokes continue through it and the bridge disappears. A «rung» between almost parallel strokes is dropped, and each junction connects its own two branches. The cross-bar of an «Н» is left alone (there is a test). Very short bridges (≤ 1.5 × width) are collapsed into one junction.
  - `hermite_join`: in a merged ink blob the skeleton follows the middle of the blob, not the strokes. So the last ≈ 1.2 × width of the branches is cut off and replaced with a cubic Hermite curve with the branch tangents. An «X» crossing gives two smooth lines without a notch.
  - `_reattach`: a branch that meets a passing stroke at a small angle (a «teardrop» loop) flows smoothly into it. A branch at a clear angle («λ») stays as it is.
  - Before/after comparison: `tools/dxf_samples.py` → `remarks2_shots/dxf_*.png`. Samples: the sample photo in two sizes and two synthetic ones (shallow crossings and merges, loops with a flourish). Number of lines in the DXF: 9 → 4, 7 → 4, 45 → 21, 9 → 7.
- **12–14.** New texts `export.dxf.desc`, `help.formats.dxf_text`, `help.formats.size_15x5` (frame margin, 0.5 mm by default).
- **15.** «Поле рамки» moved into the «Размер подписи» card. The card expands with a chevron, the field is the same, with ×/✓ and tooltips. The own size and the «нет данных о DPI» line are visible when collapsed too. The PNG card kept its chevron because «Разрешение» stayed in it.
- **16.** The height on screen 3 is shown as one line rotated by 90° (read bottom to top). The frame is centred: the left and right margins are equal. The `export.dim_height` string became single-line: «{px} px · {mm} мм».
- **17.** The right column of screen 2 scrolls (`ScrollArea`). The thin bar appears only on overflow, the mouse wheel goes through the same shared handler as on screen 3. The screen 3 column and «Параметры» already scrolled, checked at 1024 × 648. Fixed: the bar was not redrawn when only the content height changed.
- **18.** Only the chevron is left in the «Форматы по умолчанию» header.
- **19.** The app card shows «Версия 1.0» / «Version 1.0» (new i18n string `settings.version`).

Tests: 127 (were 121). New centreline checks: a shallow crossing at three angles (two whole straight lines, no bridge), a merge of almost parallel strokes, a «λ» branch at a clear angle, the cross-bar of an «Н».

## Changes per remarks 20–26 (2026-11-17, third batch, «Вноси правки»)
Backup: `_backup_before_remarks3_2026-11-17/` (+ archive and i18n in `backup_i18n/…before_remarks3`).
- **20.** The frame margin hint in `export.png.margin` and `help.formats.png_margin` now refers to the «Размер подписи» card (EN: «Signature size» card).
- **21.** «КОМПАС-3D» / KOMPAS-3D everywhere. `export.dxf.desc` = «Для AutoCAD и КОМПАС-3D, линии в мм». The format description in the card is cut with an ellipsis if it does not fit (EN at 1024 px).
- **22.** The SVG card expands. Inside is «Толщина»: radio buttons «Как в оригинале» (default, filled outline, as before) and «Заданная толщина» (stroke centrelines, `stroke-width` in mm, round caps and joins, no fill, `core/export.svg_stroke_document`). The «Толщина линии» field (0.18 mm by default, ×/✓, tooltips) **is shown only in «Заданная толщина» mode** rather than disabled: that is what the user's clarification says, and Windows 11 settings behave this way. Both values are saved (`svg_mode`, `svg_line_mm` in settings.json, validated). The SVG preview draws centrelines of the right thickness, the file size estimate takes the mode into account. Comparison: `remarks3_shots/svg_15x5.png`.
- **23.** Help texts — verbatim the approved a)–d): the frame margin moved to the description of sizes, DXF «для AutoCAD и КОМПАС-3D», a new paragraph about SVG thickness, a new `help.formats.toggles`. EN by meaning.
- **24–25.** Help (all sections) and «Свой цвет» are dialogs inside the window, like «О программе»: no system title bar, bold title, buttons at the bottom; Esc closes, Enter is the main button («Понятно» / «Добавить»). Help scrolls with the wheel, arrows and a thin bar and fits a 1024×648 window. `ui/dialogs/child.py` (ChildWindow) is no longer needed and was removed.
- **26.** Crop frame on screen 2: while dragging, the content inside the frame updates immediately. In the background the result for the whole image is computed once, and it is cropped to the frame at most once per 33 ms. The exact computation starts on release; until it arrives the quick version is shown. Along the way it turned out that every preview redraw spent ~0.4 s on the rounding mask and the frame. Now they are cached (`Preview._static`), and a redraw takes ~28 ms instead of ~430 (Xvfb, 1280×768). This also sped up dragging the «До/После» divider.
- i18n strings: changed `export.png.margin`, `export.dxf.desc`, `help.start.what2`, `help.formats.png_margin`, `help.formats.dxf`, `help.formats.toggles`. Added `help.formats.svg_thickness`, `export.svg.mode`, `export.svg.mode.original`, `export.svg.mode.stroke`, `export.svg.line`, `export.svg.line.desc` (308 in total). The CSV matches `prompt/v2` byte for byte, the xlsx is updated.
- Screenshots: `remarks3_shots/`; tools: `tools/shoot_remarks3.sh`, `tools/svg_compare.py`, scenarios `r3_*` in `tools/scenarios.py`.
- For the user to choose: EN «Original» instead of «As in original» (the size option is already called that); a shorter EN DXF description («lines in mm») so it is not cut; whether the SVG mode choice is needed in Settings › Formats.

## Changes per remarks 27–31 (2026-11-17, fourth batch)
Backup: `_backup_before_remarks4_2026-11-17/` (+ `_backup_before_remarks4_2026-11-17.rewrite_code.zip`, `backup_i18n/strings_ru_en_before_remarks4.{csv,xlsx}`).
- **27.** The EN name of the SVG mode «Как в оригинале» is «As in original». The mention in the EN help (`help.formats.svg_thickness`) was fixed the same way. The size has the same words («Как в исходнике» / As in original), but they sit under different labels («Thickness» and «Signature size») and are not confused.
- **28.** `export.dxf.desc` EN = «For AutoCAD and KOMPAS-3D, lines in mm»: fits at 1024 px without an ellipsis.
- **29.** Settings › «Форматы по умолчанию»: under the format checkboxes — a divider, the label «Толщина SVG» and two radio buttons, as in the SVG card («Как в оригинале» / «Заданная толщина»). The value is written to `svg_mode` via `set_export_default`, like the other defaults. The SVG card on screen 3 remembers its choice in `last_export.svg_mode`; a change in Settings resets this choice (`LAST_EXPORT_LINKS`). When screen 3 opens, `ex.resolve_svg_mode(last_export, svg_mode)` applies. **The SVG line thickness was not moved to Settings**: the DXF thickness is not set there either, both are remembered in their cards (`svg_line_mm`, `dxf_line_mm`), and the Settings card stays a set of choices without numeric fields. New i18n string: `settings.svg_mode`.
- **30.** «Справка» from the «…» menu is a page in the main window (`ui/pages/help_page.py`), like «Параметры». At the top «←» and «Справка» (the same geometry as Settings). On the left a list of sections in NavigationView style, as in mockups 22–26: 232 px, items 36 high, the selected one has a fill, a 3 px accent bar and semibold font. Section icons are taken from the mockups (`tools/build_icons.py help_*`). On the right the section text with a 20 px title, scrolling with the wheel and a thin bar. Esc and «←» return to the screen the help was opened from. Drag and drop, paste and Ctrl+S do not work on this page, as on the Settings page. Context help («Как подготовить фото», «Справка по форматам экспорта») stayed a dialog. Sections 24 and 25 have no table strings for subheadings, so, as in the mockups, UI labels serve as subheadings: «Рамка области», «Ластик», «Выравнивание фона», «Фильтр по цвету чернил», «AI-поиск подписи», «Тонкая настройка», «Сохранение» (`SECTION_HEADS` in `formats_help.py`). Before, these paragraphs were drawn as one line without wrapping. The page text is one continuous flow, without the icon cards of mockup 22 (left for the full help stage).
- **31.** The «Назад» button on screen 3 is `secondary`, as on screen 2 (was `ghost`, without background).
- i18n: 309 lines with the header. Changed `export.svg.mode.original`, `export.dxf.desc`, `help.formats.svg_thickness` (EN); added `settings.svg_mode`. The CSV matches `prompt/v2` byte for byte, the xlsx is updated (A1:E309).
- Screenshots: `remarks4_shots/`; tools: `tools/shoot_remarks4.sh`, scenarios `r4_*` in `tools/scenarios.py`.

## Changes per remarks 32–36 (2026-11-17, fifth batch)
Backup: `_backup_before_remarks5_2026-11-17/` (code, `tools/`, `NOTES.md`, `rewrite_code.zip`, `backup_i18n/strings_ru_en_before_remarks5.csv` + `strings_ru_en.xlsx`).
- **32.** «Толщина SVG» is a separate Settings card right under «Форматы по умолчанию», option B of the mockup (`mockup_r32`): Fluent «Line Thickness» icon (`assets/icons/svg_thickness.png`, `tools/build_icons.py svg_thickness`, SVG from Fluent UI System Icons `ic_fluent_line_thickness_20_regular`), title + caption `settings.svg_mode.desc`, on the right a ComboBox «Как в оригинале» / «Заданная толщина». With «Заданная толщина» a second row «Толщина линии» (`export.svg.line` + `.desc`) with a 0.18 ×/✓ field. The radio buttons were removed from «Форматы по умолчанию» (three checkboxes there again). The values are written via `set_export_default` to `svg_mode` and `svg_line_mm` and serve as defaults for the SVG card on screen 3. The thickness field on screen 3 stayed for quick changes: it is remembered in `last_export.svg_line_mm`, and a change in Settings resets this choice (`LAST_EXPORT_LINKS`, `ex.resolve_svg_line`). This replaces the decision in item 29 not to move the thickness to Settings.
- **33.** TextBox: the `fit` parameter is a sample that must fit entirely next to a visible «×». The width is measured with the real font: 11 + text + 3 + 30. Numeric fields («Поле рамки» on screen 3 and in Settings, width/height, DXF/SVG thickness, SVG thickness in Settings) — by «12,34», ≈81 px. R/G/B in «Свой цвет» — by «255» (13 px), ≈68 px; HEX narrowed to 148 px, the row still ends at the right edge of the «Название» field. Space for «×» — 30 px (was 32). «×» and «✓» handle the press themselves: focus returns to the field, and `break` stops CustomTkinter's "focus the pressed widget" binding. «×» does not hide while pressed. A click on an empty field, a field with a placeholder or the padding puts the cursor in the field: in placeholder mode the field is first restored, otherwise Tk does not give focus. `set()` redraws the placeholder. `SizeCard._x2` is set in `__init__`. In «Свой размер» the gap is 16 px (was 24); at 1024 px the row ends at 403 px of 407 (RU).
- **34.** Screen 3, «Размер подписи»: if a saved template is selected, a blue link «Удалить шаблон» (`export.size.delete_template`) is shown under the title, in the same style as «Сохранить как шаблон». The confirmation is the same dialog as for deleting a size in Settings (51/56, `settings.delete_size.title`), buttons «Удалить» / «Отмена». If the template was the default, the line «По умолчанию станет 15 × 5 мм» is added and the default goes back to 15 × 5. After deletion «15 × 5 мм» is selected, and the size remembered in `last_export` is reset.
- **35.** Drop-down lists. `ListPopup` measures all items with the real font: 5 + 12 + (24 swatch) + text + 12 + 5, plus 8 px for the scroll bar if the list scrolls. The width is at least the field + 8 and at most the window − 8. Items that do not fit get «…». `ComboBox.natural_width` is computed from the longest item, so the width does not jump when the choice changes. `width` is now a minimum, `max_width` is the limit after which the closed field shows «…» before the arrow. Colour: from 140 to 240 (built-ins give ≈179). DPI: from 120. Size on screen 3 — 210 (no room in the card header), long templates — with «…», the list is wider than the field. `MenuPopup` is no wider than the window − 16, text with «…». Shared `ui.theme.elide`.
- **36.** PNG resolution: 300 / 600 / 1200 DPI (150 removed), 1200 by default on screen 3 and in Settings. The downscaling filter was not changed. The settings v2 → v3 migration runs once and only changes the no longer offered 150 → 300 (in Settings and in `last_export.png_dpi`). Any other saved value, including 600, stays and serves as the default on screen 3. User decision 2026-11-17: deliberately chosen 600 DPI cannot be told apart from an automatically saved old default, so 600 is not migrated. If there is no value (new install), 1200 applies. In «Как в исходнике» `ex.effective_png_dpi` = min(chosen, photo DPI at working resolution or 300). The mm do not change, pixels are no more than those cut from the photo, the actual DPI is written to the file. The dimension labels on the preview (`export.dim_width`/`dim_height`) and the file badge show the actual px/DPI. Help `help.formats.png_res` was rewritten for the new values (RU/EN).
- i18n: 311 lines with the header (were 309). Added `settings.svg_mode.desc`, `export.size.delete_template`. Changed the texts of `help.formats.png_res` (RU/EN) and the notes of `settings.svg_mode`, `export.dpi_value`, `settings.delete_size.title`, `settings.delete_size.default_note`. The CSV matches `prompt/v2` byte for byte, the xlsx is updated (A1:E311). Script: `tools/i18n_remarks5.py`.
- Tests: 187 (were 151), new ones in `tests/test_remarks5.py`. UI tests start the app under X: without DISPLAY they are skipped, leaving 169. Among them are synthetic presses on «×»: "press → move away → release" (does not clear, focus and «×» stay), a normal click (clears, focus in the field), «✓». It was checked that without the fix these tests fail.
- Screenshots: `remarks5_shots/` (overviews `_overview_r32…36.png`); tools: `tools/shoot_remarks5.sh`, `tools/scenarios_r5.py`. The mockup scenarios `mockup_r32` were removed from `scenarios.py`: they replaced the real card.

## Stage 4 — batch processing (2026-11-17, command «Начинай»)
Backup: `_backup_before_stage4_2026-11-17/` (code, `tools/`, `NOTES.md`, plan, `rewrite_code.zip`, `backup_i18n/`). Plan: `stage4_plan.md`. No new i18n strings: all stage 4 strings were already in the v2 table, the CSV matches `/workspace/prompt/v2/i18n/strings_ru_en.csv` byte for byte, the xlsx was not changed.

**What was done**
- `core/batch.py` (new, no Tk): `Job` (one photo: edit history, result, a short summary that survives unloading the photo: export source, strokes, size, DPI, 128 px thumbnail), `Batch` (strip list, current photo, skipped files > 50 MB, «Требует внимания» state), `SaveSession` (names from the template, numbering of equal names within the batch, «Если файл уже есть» mode with «Применить ко всем», file counters), `summary_text` (three plural forms in one line), `process_job` (body of the background task).
- A batch opens if a folder or several files are dropped or chosen (including via «Открыть файл…», where several photos can now be selected). One file opens as before, without the strip.
- The first photo is processed on screen 03, the rest in the background. Background tasks are queued with low priority, user actions go first (`BackgroundWorker` became a priority queue). Each photo has its own channel: the latest request wins. A result for an outdated state version is discarded.
- Memory: at most 3 photos are fully loaded (`LOADED_MAX`, the current and recent ones), the rest keep only the summary. Switching to an unloaded photo reloads it, the preview is empty meanwhile.
- Screen 2: reason line (40), metadata with the file name (`process.meta_batch`, `batch.meta_not_found`), InfoBar «N файлов пропущено» with «Подробнее» (47) and ×, yellow bar «Требуют внимания» with «Показать» (goes to the next problem photo in a loop), green «Все файлы готовы» (42) — only if the batch had problems. Strip: «Фото N из M», «Добавить» (multi-file choice), «Убрать» (dialog 15), thumbnails with marks (✓ / «!», tooltips), arrows page through, the wheel scrolls the strip, ←/→ switch photos (not in input fields and not with open windows). «Применить ко всем» at the bottom of the right column. «Далее: экспорт» is blocked while processing is running or there are problem photos; tooltip 39 wraps at width 230.
- Screen 3: title «Предпросмотр экспорта · имя», the «нет DPI» line under the preview (63) and grey dots on thumbnails with «Как в исходнике», a strip with «Убрать» only, the card «50 фото × 2 формата = 100 файлов» + «Имена файлов: <шаблон>», the button «Сохранить в папку…» (folder choice).
- Saving: per photo, files are written one by one. The bottom line «Сохранено N из M файлов» with a progress bar and «Отмена», the main area is dimmed to 42 % and takes no input (`DimLayer`). The ⋯ menu, steps, keys and drag and drop do not work meanwhile. Dialog 44 with the «Применить ко всем» checkbox (Esc = «Отмена»). A write error — dialog 31: «Повторить» continues from the same file, «Отмена» stops. Summary 18: «Сохранено N файлов в папку «X»», «Готово», «Открыть папку».
- `ContentDialog`: a checkbox under the text (44), a file list (47, at most 8 lines), `esc_index` (Esc calls the button handler rather than just closing the window).
- Plurals: `ru_plural_text` understands «Russian one:» with a colon and strings without the few form (`batch.saving`, `batch.attention_hint`). `tn(..., forms_from=…)` takes the forms from a neighbouring string (`process.meta_batch` ← `process.meta`). The other strings give the same text as before stage 4.

**Decisions (small, mine)**
- If a file in the batch cannot be read during background loading, it is removed from the batch. Dialog 29 is shown once, for the first such file.
- The strip arrows page by a page (hence the plural tooltips: «Предыдущие/Следующие фото»), the selected photo is put in the centre of the strip, as in mockups 14 and 16.
- On «Отмена» during saving or in dialog 31 the summary with the real number of written files is shown. If nothing was written, the screen returns to the normal state. The batch after cancelling counts as unsaved («Начать заново?» will ask).
- «Отмена» in 44 skips only this photo's files that conflict. With the checkbox — the same for all following ones.
- If one batch has equal names (e.g. IMG_1 from two folders), a number is always added: «имя (2)». The same file path is not added to the batch a second time.
- «Применить ко всем» is disabled if the batch has one photo. Esc in dialog 04 = «Понятно» (processing continues).
- The batch export preview starts the frame 8 px lower (58 instead of 50) so the «Графа…» caption does not touch the size badge: in a batch the preview window is lower.

**Deviations from the mockups**
- The strip scroll bar is like Win11 Notepad's: 2 px at rest and 6 px on hover, not a constant 5 px.
- Thumbnails are real photos: a square around the found signature, for a photo without a signature — the centre of the sheet. In the mockup they are drawn.
- The frame in the export preview fills the window (remarks 10/16), so on 16/17/18/63 it is larger than in the mockup.
- All 16 conflict decisions from the plan are kept: PNG 300/600/1200 (1200 by default), «Как в исходнике» without upscaling, DXF description «КОМПАС-3D, линии в мм», «Назад» secondary, dialogs inside the window, Ctrl+S as before, etc.

**Tests**: `python -m pytest -q tests` under Xvfb → **213 passed** (+22 in `tests/test_stage4.py`: batch model, plurals, names and save modes, queue priorities, a real batch scenario in the app: opening a folder, «Требует внимания», ←/→, «Убрать», «Добавить», skipping > 50 MB, «Применить ко всем», last photo → screen 1, saving all files, a repeat with numbers, «Отмена» with the real number, dialog 44 with «Применить ко всем», one file without the strip).

**Screenshots**: `stage4_shots/` — 14 states (14, 15, 16, 17, 18, 38, 39, 40, 41, 42, 44, 46, 47, 63) × RU light / RU dark / EN light at 1280 and RU/EN light at 1024 × 616. `stage4_shots/compare/` — the app next to the mockup. Overviews: `overview_light.png`, `overview_dark.png`, `overview_en_light.png`, `overview_light_1024.png`, `overview_compare_*.png`. Test data: `testdata/batch50` (50 photos, 2 without a signature, every 9th without DPI), `testdata/batch50ok`, `testdata/batch_large` (sparse files > 50 MB). Tools: `tools/make_batch.py`, `tools/scenarios_s4.py`, `tools/shoot_s4.sh`, `tools/s4_sheets.py`.
- Help (25, section «Пакетная обработка») was done earlier. Its text about «Требует внимания» («если программа не уверена…») is wider than decision 1 (only «подпись не найдена»). The string was not changed: it is a v2 table text.

## Changes per remarks 37–44 (2026-11-18, sixth batch, «Вноси изменения»)
Backup: `_backup_before_remarks6_2026-11-18/` (code, tools, NOTES, zip, CSV/xlsx before the edits).

- **37 Settings reset.** In Settings after «Сведения» a «Сброс» section with the card «Восстановить параметры по умолчанию» (no caption, reset icon) and a red «Сбросить» button (`kind="danger"`, #B22222 / white text in both themes; tokens `danger*`, `on_danger` in `ui/theme.py`). The dialog is like «О программе»: «Сбросить настройки?», red «Сбросить» + «Отмена», Esc = «Отмена». `SettingsManager.reset_to_defaults()` keeps `custom_sizes`, `custom_colors`, `settings_version`, the rest (and `last_export`) goes to defaults. Theme and language apply at once (`App.reset_settings`), work on screens 2–3 is not touched.
- **38** The button «Применить настройки ко всем» (`batch.apply_settings_all`), before applying — the dialog «Применить настройки ко всем?» with the number of other photos (`tn`, blue «Применить» + «Отмена», Esc = «Отмена»). The key `batch.apply_all` stayed for the checkbox in dialog 44.
- **39** «Начать заново?» by the snapshot `_work_token` = (id and version of each photo, export settings key), which is written on a successful save (single and batch). A failed or cancelled save resets the snapshot. Fixed B7 (Ctrl+Z/Y in a batch changes the version), B8 («Убрать»/«Добавить» change the list), S6/B4 (export settings are part of the snapshot). «Назад»/«Далее» do not change the snapshot.
- **40** `core/export._trace_resolution`: `ppm = max(min(40, max(src_ppm, 20)), src_ppm)` (the 3000 px limit is kept). Photo 3 at 15×5: centreline 7.8 mm in 40 pieces → 37.3 mm in 15 (as with «Как в исходнике»). Test on `tests/data/sample3.png`.
- **41** All Help sections are cards with icons as in mockups 22–26 (icons `assets/icons/hc_*.png` from the mockup SVGs, `tools/svg_extract_help.py` + `tools/build_icons.py`). The texts were not changed, names in «…» are in semibold. The «Форматы экспорта» window from screen 3 has the same cards, title as in «О программе».
- **42** «Подготовка фото»: a block of examples (a large «Хорошо» + 2×2 bad ones, photos `assets/help/ex_*.png`, `tools/build_help_examples.py`) above the cards — on the Help page and in the window from screen 1. The window title is as in «О программе» (remark 24), there is no «Ещё несколько советов» block. The tiles shrink proportionally, at 1024 × 680 the captions wrap.
- **43** «Если файл уже есть» defaults to «Спрашивать» (`if_exists = "ask"`), reset returns «Спрашивать». An already saved choice is not changed (no migration: an auto-saved «Добавить номер» cannot be told apart from a chosen one).
- **44** Help › «Форматы экспорта»: the card «Шаблон имени файла» (approved text, last). The caption in Settings: «Метки: {имя}, {дата}. Например, подпись_{имя}_{дата} → подпись_IMG_3051_2026-11-18.png» (EN — Tokens…). The Settings card can wrap the caption to two lines, but at the minimum width the text fits in one (RU 525 px, EN 528 px of ~640).
- Line wrapping (`wrap_runs`): a word split between parts of different styles (e.g. «_» + «.») is wrapped whole, a dot is not left alone on a line.
- i18n: `tools/i18n_remarks6.py`, +16 strings, 327 lines with the header; the project CSV and `/workspace/prompt/v2/i18n/strings_ru_en.csv` are byte-identical.
- Tests: `tests/test_remarks6.py` (+16), the old Help tests were moved to cards, `test_stage4` presses «Применить» in the new dialog and explicitly sets «Добавить номер».
- Screenshots: `remarks6_shots/` (RU light/dark, EN light at 1280 × 768; `*_min.png` — 1024 × 648, i.e. a 1024 × 680 window). Scenarios: `tools/scenarios_r6.py`, `tools/shoot_remarks6.sh`.

## Remark 45 (2026-11-18, «Вноси правку»)
Backup: `_backup_before_remark45_2026-11-18/`.
- Help › «Пакетная обработка» › «Настройки для всех фото» (`help.batch.all_text`): «Кнопка «Применить настройки ко всем» переносит…» (EN «Apply settings to all copies…»). There are no other mentions of the button in the help. The checkbox string `batch.apply_all` («Применить ко всем» in the «Если файл уже есть» dialog) is untouched.
- `tools/i18n_remark45.py`; the project CSV and prompt/v2 are byte-identical, 327 lines. Test `test_r45_help_names_the_new_button_and_checkbox_is_kept`.
- Screenshots: `remarks6_shots/light_r45_help_batch.png`, `en_light_r45_help_batch.png`, `light_r45_help_batch_1024.png` (1024 × 680).

## Stage 5 (2026-11-18, plan `stage5_plan.md`, «Решения пользователя»)

Backup: `_backup_before_stage5_2026-11-18/`. AI search (`core/ai.py`) is a separate stage, not included.

1. **«Размеры подписи» (36, 37, 49, 51, 52, 56).** Size rows 40 px apart, «…» on each row, a «По умолчанию» badge, a «Добавить размер» button. The menu of a built-in size has only «Сделать по умолчанию» (disabled for the current one, 52); of an own size also «Изменить», a divider, «Удалить» (36). Dialog `ui/dialogs/sizes.py::SizeDialog` (37/49): «Название», «Ширина, мм», «Высота, мм» (numbers centred), a wrong number — a beep and focus in the field; an empty name → «W × H мм». Deletion — the shared `confirm_delete_size` for Settings and «Удалить шаблон» on screen 3: title «Удалить размер «Имя · W × H мм»?» (as on 51; a long title wraps — `ContentDialog` can now do a multi-line title), the line «По умолчанию станет 15 × 5 мм» only for the default, red «Удалить» (#B22222), Esc = «Отмена». On the right of the card header — the default size.
2. **Own colours.** A right click on an own colour in the open «Цвет подписи по умолчанию» list → the «Удалить» menu with a trash can (no confirmation, as on screen 3). The list stays visible under the menu (`Popup.grab_over_next`). Deleting the default colour → «Синий». Logic — `Settings.delete_custom_color`, shared with screen 3.
3. **«Сообщить о проблеме».** `App.report_issue` / `issue_url`: `…/issues/new?body=…` without a title, the body in English (`issue.body`): version, Windows (registry `CurrentBuild`/`DisplayVersion`), graphics card (DXGI, fallback wmic), DirectX 12, language. URL ≤ 2000 characters. The link in «О программе» works the same way.
4. **Updates.** `core/updater.py` (no Tk) + `ui/updates.py` (`UpdateController`) + `ui/dialogs/update.py` (32). A silent check 3 s after start if «Проверять обновления при запуске» is on and 24 h have passed (`last_update_check`, not reset by «Сбросить настройки»); no network — silence and a retry on the next start. Window 32 after a silent check appears only on screen 1 (waits until the user returns there). «Позже» and Esc — until the next day. «Проверить сейчас»: a new version → 32, otherwise a grey line under «Проверять обновления при запуске» («Установлена последняя версия (1.0)» / «нет подключения»), it disappears when Settings close. «Скачать» → in the same window «Скачивание… N %», a bar and «Отмена» (the file is deleted); a broken download → «Не удалось скачать обновление»; SHA-256 from the `.sha256` asset (or from the release text) does not match → «Файл обновления повреждён, попробуйте ещё раз», the file is deleted; it matches → the installer starts and the program closes. Network — in separate threads, the result via a queue into Tk.
5. **DirectX 12.** `platform_win.dx12_supported()` (`D3D12CreateDevice` with level 11_0, `SE_FORCE_DX12=0/1` for tests). Without DX12 the toggle is disabled and shows a grey «Откл.» (the saved choice is not changed), under the description a grey line «Видеокарта не поддерживает DirectX 12, используется процессор». AI processing gets `gpu = setting and DX12`.
6. **Esc.** Esc in an input field cancels the edit and removes focus; a second Esc closes Settings/Help. In a dialog Esc = «Отмена». On screens 1–3 without windows Esc closes nothing.
7. **Language.** Switching RU→EN with Settings/Help open translates all texts (test: no Cyrillic is left on the canvases).
8. **Width.** Settings and Help: the column is no wider than 1000 px, centred in the window (2k_25, 2k_27); «Назад» and the title move with the column; the scroll bar is at the window edge. At 1024 and 1280 everything is as before (1280: a 1000 px column with 140 margins).
9. **Help texts.** A test checks that every `help.*` key is shown. Differences on 64–67 per remarks 1, 2, 18, 29, 32, 35 are intentional.

**i18n**: +3 strings (`update.downloading`, `update.download_failed`, `issue.body`), 330 lines with the header in total; the project CSV is byte-equal to `prompt/v2`, the xlsx is updated (`tools/i18n_stage5.py`).

**Tests**: 253 passed (+16 `tests/test_stage5.py`, +7 `tests/test_updater.py`). Tests do not go online (`SE_NO_UPDATE_CHECK=1` in conftest, stubbed `fetcher`/`opener`). `App` clears the `gfx` image cache on creation (one test run has several Tk instances).

**Screenshots**: `stage5_shots/` (`tools/scenarios_s5.py`, `tools/shoot_s5.sh`): RU light / RU dark / EN light at 1280 × 768, the minimum window `_1024` (1024 × 648 client area), the wide `_2k` (2560 × 1400).

**Check on Windows**: DX12 detection and the graphics card name via DXGI, the Windows version from the registry; starting the installer and closing the program; a real GitHub release with the assets `SignatureExtractor-<ver>-setup.exe` and `.sha256`; behaviour without network and behind a proxy; the issue URL length in the default browser; the 1000 px column at 125–150 % scale.

## Remarks 46–58 (2026-11-18, seventh batch, «Вноси правки»)
Backup: `_backup_before_remarks7_2026-11-18/` (the name `_backup_before_remarks6_…` is already taken by the copy before 37–44). Screenshots: `remarks7_shots/` (`tools/scenarios_r7.py`, `tools/shoot_remarks7.sh`), RU light.

- **46** — the update window while downloading: «Отмена» of normal width, on the right (`ui/dialogs/update.py`).
- **47** — «Цвет подписи по умолчанию» is an expandable card with a list of colours, «⋯» on each: «Сделать по умолчанию» (disabled for the current one), own colours also have «Изменить» and «Удалить» (confirmation; if the default colour is deleted — «По умолчанию станет Синий»). The button «Добавить цвет», the window «Изменить цвет» (`ui/dialogs/colors.py`, `color_dialog.py`, `settings_page.py`).
- **48** — auto-detection doubts (`core/processing.assess_doubts`): pale (<45), many fragments (>40), the frame cuts strokes (>1 % of the ink of crossed strokes outside the frame, the photo edge does not count; only for the auto frame), few strokes, too dense (>0.25), stamp/red ink (red–orange hue angle; also red stamp lines inside the frame ≥0.25 of the signature), several signatures (≥0.25; only for the auto frame). A doubt is the same yellow mark and bar, export is not blocked (the bar without the «экспорт недоступен» line); only «не найдено» blocks. `Job.status = doubt`, `BatchState.blocking()`.
- **49** — help texts, a new «Параметры» card in «Начало работы»; in the formats help — «Значение по умолчанию задаётся в параметрах».
- **50** — the «Толщина DXF» card (mm field + ✓) in «Экспорт»; a quick edit on screen 3 is stored in `last_export.dxf_line_mm`.
- **51** — order of «Экспорт»: formats, sizes, frame margin, colour, PNG, SVG, DXF.
- **52** — auto ink: blue/purple is preferred over red (≥60 px and ≥8 % of the coloured ones).
- **53** — a long separate flourish is joined to the auto frame (elongation ≥4:1, overlap ≥25 %, gap ≤ max(thickness, 12 mm), length ≤2× the signature and ≤0.9 of the page).
- **54** — DPI ≤72 (and >4800) counts as missing.
- **55/56** — hue filter in the found colour: almost black auto ink does not let printed text through, pale stamp outlines are cut off.
- **57** — the auto frame takes crossed strokes whole (each side grows by at most 25 %).
- **58** — screen 3: colour swatches wrap to a new line, the «Удалить цвет» link under them (only for own colours), a right click also asks for confirmation.

Regression: `r48_try/regress.py` — 59/59 clean PNGs of zip3 without marks; p3 → «печать», p4 → «несколько подписей»; photo 4 is not cropped. Tests: `tests/test_remarks7.py` (28), 281 in total.

## Remarks 59–71 (2026-11-18, eighth batch, «Вноси изменения»)
Backup: `_backup_before_remarks8_2026-11-18/` (code, tools, NOTES.md, rewrite_code.zip, i18n csv+xlsx). Screenshots: `remarks8_shots/` (`tools/scenarios_r8.py`, `tools/shoot_remarks8.sh`), RU light.

- **59** — auto frame: among groups with ≥0.25 of the leader's ink, a signature is preferred over a handwritten full name/date: score = ink × max(0.25, min(1, share of the three largest pieces / 0.8))² (`_best_group`).
- **60/61** — help texts as in the record (`help.formats.color`, `help.process.ink_auto`, `help.process.frame1`, `help.prep.paper_text`, `help.process.frame4`).
- **62** — doubt reasons as a note line (InfoBar type `note`: a triangle + 12.5 px text without fill, cut with «…» and a tooltip) under the yellow bar, joined with «; » (`batch.doubt.*`).
- **63/64** — auto ink on a blue stamp: if the found colour is coloured (C ≥10) and there is a noticeably darker group (L* lower by ≥20, neutral C<14 or hue differs by >40°, ≥60 px and ≥0.3 of the ink pixels), that one is taken (median of the darkest 5 %), the photo is marked `stamp_like`, colour tolerance 26 instead of 30. Blue is preferred only if L* ≤48.
- **65** — criterion 8 `ink_stamp` «Цвет чернил похож на печать»: `stamp_like` or a light blue (L* >48, C ≥10). It also fires after a successful colour replacement (per the record).
- **66** — «Исключить цвет» in «Вручную» mode (per mockup r66): a second «Пипетка», a swatch, «×»; alpha weight clip(0.5 + (dₑₓ−dᵢₙₖ)/12) in Lab. In «Авто» it is saved in the parameters but not applied.
- **67** — table lines >15 mm (opening with line kernels ±3°, only a grid — a horizontal touches a vertical) are removed from the masks before the auto frame and criteria 3/7. Ordinary ruling without verticals is not removed (otherwise straight strokes of photo 1 were cut).
- **68** — «много обрывков» counts only fragments >1 mm².
- **69** — all 8 help items, item 2 with correction 70.
- **70** — one photo: the «Требует внимания» bar (without «Показать») and the reason above the image; only for doubts, «не найдено» — the earlier window.
- **71** — «⋯» → «Начать заново» (icon `reset`, third item, before the divider): always the `dialog.restart.*` dialog, then screen 1; disabled on screen 1 without a photo. A sentence was added to `help.batch.add_remove_text`.

**i18n**: 356 lines with the header (`tools/i18n_remarks8.py`), the project CSV is byte-equal to `prompt/v2`, the xlsx is updated. The text of the former `help.process.frame4` in the size line is a new key `process.meta.frame_large`.

Regression: 59/59 clean PNGs of zip3 without marks, 0 changes on 81 files (zip3 + testdata) except marks; p3 → `stamp_ink`, p4 → `stamp_ink several` (the left signature is on the stamp); photo 4 is not cropped. zip4: blue photos — dark ink, the frame on the signature, mark `ink_stamp`; yellow ones — the frame narrowed to a table row, but the date gets into it, the stamp and lines stay inside, the ink colour is olive, mark `busy`. Tests: `tests/test_remarks8.py` (18), 299 in total.

## Remarks 72–76 (2026-11-18, ninth batch, «Внеси последние изменения»)
Backup: `_backup_before_remarks9_2026-11-18/` (code, tools, NOTES.md, rewrite_code.zip, i18n csv+xlsx). Screenshots: `remarks9_shots/` (`tools/scenarios_r9.py`, `tools/shoot_remarks9.sh`), RU light. Moved over from the approved prototype `r72_73_try` one to one (without the `EXP_*` flags).

- **72** — ruling in the ink colour (`core/ruling.py`): straight lines ≥25 mm that extend beyond the rest of the ink by ≥5 mm on both sides, lone ones ≥60 mm or ≥0.6 of the photo long are removed; pixels where they cross strokes stay. In a table (yellow form) all straight lines are removed.
- **73** — tinted paper (`core/tinted.py`, paper chroma ≥20): white balance, separating «ink/stamp» by the «yellowness» of pieces, a frame by the table cell (`table_cells`, `merge_by_cells`), «несколько подписей» — only within one column, the ink colour corrected for the paper tone; `clean()` stitches strokes cut by lines, removes leftover dashes and dust; serifs on table lines are removed (only crossings and stroke ends stay). A prototype bug was fixed: morphology on a crop around lines counted the crop edge as ink (`_morph` pads the crop with blank paper) — the regression result did not change.
- **74** — one photo, signature not found: instead of window 30 a yellow «Требует внимания» card with the reason `batch.reason_not_found` under the image (as in a batch), without the strip and «Показать»; «Далее» is disabled. The `errors.no_signature.*` strings stayed in the table but are unused.
- **75** — not done (AI postponed).
- **76** — `cv2.setRNGSeed(12345)` before kmeans: the result is repeatable.

**i18n**: no new strings, the CSV is byte-equal to `prompt/v2`.

Regression (`tools/regress_r9.py`, `tools/regress_r9_cmp.py`, 133 files): matches the prototype on all 133. 18 changed: three yellow zip4 photos (507/526/536: 5/9/8 pieces, frame on the signature, blue colour, no marks) and 15 synthetic `*__rule_ink` (ruling removed, frame as in `__base`). 59 clean PNGs of zip3 unchanged and without marks, photo 4 is not cropped, photo 1 and the synthetic `__base`/`__rule_grey` unchanged. Test r53 was redone: a straight «flourish» far beyond the signature now legitimately counts as ruling, an arc replaces it. Tests: `tests/test_remarks9.py` (15), 314 in total. Time (`tools/time_r9.py`, best of 5): yellow ones ~2.0–2.2 s instead of ~0.9 s, the others +0.05–0.2 s.

## Remarks 77–85 (2026-11-19, tenth batch, «Вноси замечания 77–85»)
Backup: `_backup_before_remarks10_2026-11-19/` (code, tools, NOTES.md, rewrite_code.zip, i18n csv+xlsx). Screenshots: `remarks10_shots/` (`tools/scenarios_r10.py`, `tools/shoot_remarks10.sh`), RU light.

- **77** — one photo with a doubt: the yellow «Требует внимания» panel and the reason line are now under the image (bottom to top: the reason at the bottom edge of the column, the panel above it, the «штрихи · мм» line above the panel), as with the «не найдена» card and in a batch. The help text `help.batch.attention_text` was refined.
- **78** — AI removed from v1.0: no «AI-поиск подписи» and «Ускорение на видеокарте» toggles, the «Обработка» section in Settings was removed (it had only them), the keys `ai_default`/`gpu_acceleration` were removed from settings (an old settings file with them is still read), the AI step was removed from `core/processing.py`, `onnxruntime` from `requirements.txt`, the AI card from the formats help. The tips «подпись не найдена», «сложный фон», «большая рамка» mention only the frame and eraser. Stage 6 has no model and no onnxruntime (remark 75 cancelled). Kept: «Сообщить о проблеме» still includes GPU/DX12 diagnostics.
- **79** — the scroll bar as in Windows 11 (Notepad): at rest a 2 px line 4 px from the edge; on hover it smoothly (~120 ms) widens to 6 px, a 12 px track and 8×6 arrows appear; it narrows ~1 s after the pointer leaves. Arrows — a step (with auto-repeat), a click on the track — a page, the thumb can be dragged. Applied to page bars and drop-down lists; the horizontal bar of the batch strip was not changed.
- **80** — keyboard shortcuts work with any layout: the letter is determined by the key code (Windows VK, X11 evdev), not by the keysym (`ui/keys.py`, a single `<Control-KeyPress>` handler). In input fields with a Cyrillic layout Ctrl+A/C/V/X/Z/Y work too.
- **81** — log `%APPDATA%\Signature Extractor\signature_extractor.log` (rotation 1 MB × 3, UTF-8, `core/logs.py`); unhandled exceptions (sys/threading/Tk) are written. All caught errors are logged (51 places, including 18 "silent" `pass`); only `queue.Empty` is not logged (it is not an error). An AST test checks that there are no new silent `except`.
- **82** — app state moved to `core/state.py` (`AppState`); `App` accesses it via properties, nothing changed outwardly.
- **83** — the save folder is fixed on the first start (`Settings.fix_save_folder`) and does not change when the language changes. For upgraded users it is fixed on the next start; after «Сбросить» it is chosen again in the current language. The file name template still depends on the language.
- **84** — release v1.0: in stage 6 the tag `v1.0` (not v1.0.0); the «Что нового» link and the «О программе» window lead to `releases/tag/v1.0`.
- **85** — no full stop at the end: «Сбросить настройки?» (`dialog.reset.body`), «Применить настройки ко всем?» (`dialog.apply_all.body`), the large-frame hint (`process.meta.frame_large`), RU and EN.

**i18n** (`tools/i18n_remarks10.py`): only the app table was edited; `prompt/v2/i18n/strings_ru_en.csv` was not changed. Approved differences from `prompt/v2` (checked by `tests/i18n_prompt_diff.py`, the byte-for-byte tests were switched to it):
- changed (10): `import.tip_background`, `process.meta.frame_large`, `batch.reason_not_found`, `help.process.frame4`, `help.start.settings_text`, `help.prep.paper_text`, `help.batch.all_text`, `help.batch.attention_text`, `dialog.reset.body`, `dialog.apply_all.body`;
- removed (10): `process.ai`, `process.ai_desc`, `settings.ai_default`, `settings.ai_default.desc`, `settings.gpu`, `settings.gpu.desc`, `settings.gpu.unsupported`, `help.process.ai`, `errors.no_signature.title`, `errors.no_signature.body`.
The table has 346 lines (was 356).

Tests: `tests/test_remarks10.py` (24), 337 in total (was 314; the GPU toggle test was removed). All pass.

## Remarks 86–89 (2026-11-19, eleventh batch, «Вноси изменения и заливай на github»)
Backup: `_backup_before_remarks11_2026-11-19/` (code, tools, NOTES.md, rewrite_code.zip, i18n csv). Screenshots: `remarks11_shots/` (`tools/scenarios_r11.py`, `tools/shoot_remarks11.sh`), RU light, synthetic photos only. Four new tips without AI were approved (77–85).

- **86** — the batch strip scroll bar is like the other Windows 11 bars (79): at rest a 2 px line about 4 px under the thumbnails (where it was); on hover it smoothly (~120 ms) widens to 6 px in the middle of a 12 px track, arrows ◀ ▶ (8 × 6, rotated) appear at the ends; it narrows ~1 s after the pointer leaves. An arrow moves by one thumbnail (with auto-repeat), a click on the track by a page, the thumb can be dragged, the wheel works. The round «‹» / «›» buttons at the strip stayed. Shared code — `scroll.hbar_geometry` / `hbar_zone`, `draw_bar` draws the horizontal bar too.
- **87** — file name template: checked, it already works like this — while the template has not been changed by hand (`None` in settings), it follows the language («подпись_{имя}» ↔ «signature_{name}»); after a manual change it stays as entered; if the default template of the current language is entered, it follows the language again. The code was not changed, a test was added.
- **88** — the «Graphics card» and «DirectX 12» lines were removed from «Сообщить о проблеме»; `platform_win.dx12_supported`, `gpu_names`, `_dxgi_adapters` were deleted. The issue keeps the version, Windows and language.
- **89** — in all «Требует внимания» cases (one photo with a doubt, one photo «не найдена», a batch with a doubt, «не найдена» in a batch) the reason is the second line inside the yellow card; several reasons are separate lines inside (the card grows by 16.9 px per line). The separate line with ⚠ under the card and the reason bar above the preview (mockup 40) were removed. In a batch, if the selected photo has no reason, the second line stays «Поправьте их или уберите из пакета…» (while there are photos without a signature). Help `help.batch.attention_text`: «а в ней — причина для выбранного фото».

**i18n** (`tools/i18n_remarks11.py`, only the app table, `prompt/v2` was not changed). Added to the 77–85 differences: changed `issue.body` (88: without the Graphics card / DirectX 12 lines), `help.batch.attention_text` changed once more (89). In total 11 strings changed, 10 removed, 346 lines.

Tests: `tests/test_remarks11.py` (11), 348 in total, all pass.

## Remarks 90–91 (2026-11-19, twelfth batch, «Вноси изменения и заливай на github»)
Backup: `_backup_before_remarks12_2026-11-19/` (code, tools, NOTES.md, rewrite_code.zip, pending_rewrite.md). Screenshots: `remarks12_shots/` (`tools/scenarios_r12.py`, `tools/shoot_remarks12.sh`), RU light, synthetic photos; `light_r12_compare_mockup38.png` — next to mockup 38.

- **90** — in a batch, if the selected photo has no reason of its own (while others have no signature found), the yellow card has no second line «Поправьте их или уберите из пакета, чтобы перейти к экспорту» — only «N файлов требуют внимания» and «Показать» (height 48). This is a deliberate difference from mockups 38–41. The string `batch.attention_hint` was removed from the app table (`tools/i18n_remarks12.py`).
- **91** — a copy of the prompt `/workspace/prompt/v2` (stages, `final_prompt_ru.md`, `CHANGES.md`, the strings table csv/xlsx) is in `docs/prompt_v2/` (not edited, only `README.md` was added). Tests take the prompt table from there, the fallback path is `/workspace/prompt/v2` (`tests/i18n_prompt_diff.PROMPT_DIR`). Personal data check: no signers' surnames, email addresses, phone numbers or photos; only the author's name («© 2026 Stanislau Salavei», repository links, and a sample path `C:\Users\<name>\Documents\Подписи` — also in the app table; the user name in it was replaced with a neutral «User» on 2026-11-20). The PNG/HTML mockups (`/workspace/mockups`) are not in the repository — tests do not need them. Tests with real photos (`/workspace/rewrite/r48_try`, `/workspace/private_test_data/sample3.png` = photo 3) are skipped with a reason without them; a test (AST) checks this. Local tests and comments were also switched to «photo N» and an md5 of the name.

**i18n**: the removed string `batch.attention_hint` (90) was added to the differences from `prompt/v2`. In total 11 strings changed, 11 removed.

Tests: `tests/test_remarks12.py` (4), 352 in total, all pass.

## Stage 6: installer and release (2026-11-19, «Начинай», plan `stage6_plan.md`, decisions D1–D11) + remark 92
Branch `stage-6` from `develop`, a PR into `develop` (not merged); `main`, the `v1.0` tag and the release were not touched — only on the user's command.

- **Version in one place** — `core/version.py` (`VERSION = "1.0"`, `RELEASE_TAG = "v1.0"`); `ui/app.py` and `ui/pages/settings_page.py` take it from there. Next versions (D8): `v1.0.1` — fixes, `v1.1` — new features.
- **Build (D1, D3)** — `packaging/build.py`: the exe version file (`build/version_info.txt`), PyInstaller onedir from `packaging/SignatureExtractor.spec` (windowed without a console, `app.ico`, no UPX, resources `assets/`, `i18n/`, LICENSE; hidden imports `PIL._tkinter_finder`, pillow-heif; no onnxruntime/model — remark 78), then ISCC and `SignatureExtractor-<ver>-setup.exe.sha256` (`sha256sum` format). `--version 1.0.1` — a test build of another version. No code signing (D4).
- **Installer** — `packaging/installer.iss` (UTF-8 with BOM): for the current user only (`PrivilegesRequired=lowest`, no UAC), `%LOCALAPPDATA%\Programs\Signature Extractor`, Windows 10 1809+ x64 (`MinVersion=10.0.17763`, `x64compatible`), languages en/ru by the Windows language (otherwise English), a read-only GPLv3 page (`InfoBeforeFile`, D6), a Start menu shortcut always, a desktop one — a checkbox (unchecked), shortcuts and the post-install launch pass `--installer-language ru|en`. The name in «Installed apps» is «Извлечение подписи (Signature Extractor)» (D9). A constant `AppId`, upgrade in place, the old version's `_internal` is removed; `AppMutex` + Restart Manager ask to close the running program; `%APPDATA%\Signature Extractor` is not touched.
- **Update from the program (D5)** — the installer is started with `/SILENT /SP- /CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS` (only the progress window), the program releases the mutex before starting it; the new version is opened by the installer itself. `SE_UPDATE_API=<…/releases/latest of a test repository>` overrides the check address (D7).
- **GitHub Actions** — `.github/workflows/build-installer.yml` (`windows-latest`; while the box token lacks the `workflow` scope, the file is in `packaging/ci/` and is moved with one `git mv`): a PR into develop/main and a manual run → tests without UI, build, exe self-check (`SE_SMOKE_REPORT`, `ui/smoke.py`: drag and drop, HEIC, OpenCV, ImageTk, DXF, no errors in the log), an artifact with the installer and `.sha256`. A `v*` tag (only on the user's command) → a DRAFT release with the notes `docs/release_notes/<tag>.md` and a SHA-256 line; only the user can publish it (D2).
- **Release notes (D11)** — RU/EN draft `docs/release_notes/v1.0.md`, awaiting approval.
- **92** — the window remembers its size (normal, not maximized) and the «maximized» state in `settings.json` (`window`, logical pixels), but not its position: the window opens centred in the monitor's work area. A saved size larger than the current screen is reduced to fit (taking the title bar and scale into account), one below the minimum is increased to 1024 × 648 (if the screen allows). «Сбросить» does not touch the window size. `core/window_geom.py`, `App._apply_initial_geometry / save_window_state`, `platform_win.work_area / frame_extra`.

Tests: `tests/test_stage6.py` (35: installer, workflow, build, update flags, `SE_UPDATE_API`, window 92 — logic and the real window, self-check). 387 in total.

## Remark 93 (2026-11-19, «перед релизом 1.0») — update check: diagnostics and a false «нет подключения»
Backup: `_backup_before_remark93_2026-11-19/`. No new i18n strings.
- `check_latest` writes every failure to the log as a WARNING: address, error class, HTTP code; on 403/429 — the remaining rate limit and reset time (`X-RateLimit-Reset`, local time) (`updater.describe_error`). The traceback is still DEBUG.
- HTTP 404 from `…/releases/latest` (the repository has no published release yet) = «Установлена последняя версия ({version})», not «нет подключения» (WARNING in the log). A 404 from another address (e.g. `…/releases/tags/vX`) — «нет подключения» as before.
- `UpdateController` writes the check address in use to the log (INFO) on creation, marked `(SE_UPDATE_API)` if it is overridden.
- `api_url()` trims spaces, quotes (`"`, `'`, «», “”, ‘’), NBSP, BOM and zero-width characters at the edges; a value that is still not an http(s) address after that (or has a space inside) is rejected with a warning in the log, and the project address is used.

Tests: `tests/test_remark93.py` (local HTTP server: 404/403/500/broken JSON/connection refused, value trimming, warnings, controller without Tk).

## Installer polish (2026-11-20, «Вноси изменения»)
Backup: `_backup_before_installer_2026-11-20/` (outside the repository). The design mockups are not in the repository.
- **Images** — `packaging/installer/`: the left panel of the Welcome and Finished pages (`wizard_image_ru_*.png`, `wizard_image_en_*.png`: app icon, program name, «PNG · SVG · DXF», a synthetic signature on a pale blue background) and the icon of the inner pages (`wizard_small_*.png`: app icon with a transparent margin), PNG in all Inno Setup 6.6 DPI sizes (7 + 7 + 7). `WizardImageFile` takes the Russian images; for English installs `[Code]` loads the English image of the nearest size. Requires Inno Setup 6.6+ (`#error` otherwise).
- **Pages** — the Welcome page is on (`DisableWelcomePage=no`): what the program does, «no administrator rights», a short GPLv3 note with a clickable link (`TNewLinkLabel`) instead of the full licence page (`InfoBeforeFile` removed; `LICENSE.txt` is still installed). The Ready page lists the install folder (`AlwaysShowDirOnReadyPage=yes`, the folder page stays hidden). Finished: «Установка завершена», the «Запустить программу» check box is ticked. Page texts use the short name «Извлечение подписи» / «Signature Extractor»; the window title keeps «Установка — Извлечение подписи (Signature Extractor) <version>».
- **Programs and Features** — `AppComments` (RU/EN, by the install language).
- **CI** — after the build, `packaging/installer_screenshots.ps1` installs the program in Russian and English on the runner and saves each wizard page as PNG (artifact `installer-screenshots-<version>`, best effort, never fails the build, not for tags).

Tests: `tests/test_stage6.py` — licence note and link, page texts, image sizes.
