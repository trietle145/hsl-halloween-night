# Dashboard build guide (Tableau Public)

Data: `data/exports/` (rebuild with `python src/export.py`).

## Design

**Layout** (fixed 1200 × 820):

```
┌──────────────────────────────────────────────────────────────────┐
│ Halloween on HSL                          [Saturday ▾] [Routes ▾] │ header
│ Planned departures, Sat 00:00 → Sun 04:00 · …                    │
├────────────────────────────────┬─────────────────────────────────┤
│                                │  511,897     266       11        │ BANs
│                                │  planned     routes    on All    │
│                                │  departures  running   Saints'   │
│          ROUTE MAP             ├─────────────────────────────────┤
│          (~720 × 640)          │  Departures per hour             │
│                                │  stacked bars                    │
│                                │                                  │
│                                │  ■ Bus ■ Tram ■ Metro ■ Train …  │ legend
├────────────────────────────────┴─────────────────────────────────┤
│ Data: HSL GTFS via Mobility Database, CC BY 4.0 · planned only    │ footer
└──────────────────────────────────────────────────────────────────┘
```

**Colours** (validated for colour-blind separation; buses stay a quiet neutral because they are 85% of departures):

| Role | Hex |
|---|---|
| Background | `#FCFCFB` |
| Text, primary | `#0B0B0B` |
| Text, secondary | `#52514E` |
| Text, muted / axes | `#8A8984` |
| Grid lines | `#EBEAE6` |
| **Bus** | `#B9B7AE` |
| **Tram & light rail** | `#1BAF7A` |
| **Metro** | `#EB6834` |
| **Train** | `#8C4799` |
| **Ferry** | `#2A78D6` |

**Fonts:** use Tableau's own fonts, because they render the same on Tableau Public web.
- Title: Tableau Semibold 20
- Subtitle: Tableau Book 11, secondary
- BAN number: Tableau Semibold 26, primary
- BAN label: Tableau Book 9, secondary
- Axes and legends: Tableau Book 9, muted

**Rules:** colour always means mode (never rank). No dual axes. No numbers on every bar; tooltips carry the detail. Use light grid lines and no borders.

---

## 1. Data sources (two, kept separate)

1. **hourly**: `hourly.csv` (already connected).
2. **Data → New Data Source → Spatial file → `route_lines.geojson`**.

Check the field types on the Data Source page: in `hourly`, `Hour` should be **date & time** (calendar-clock icon) and `Window Hour` / `Departures` should be numbers (#).

## 2. Parameters (these drive both data sources at once)

Make these in the Data pane: ▾ menu → **Create Parameter**.

**`Saturday`**: String, *List*:

| Value | Display as |
|---|---|
| `halloween` | Halloween · Sat 31 Oct |
| `baseline` | Ordinary Saturday · 17 Oct |

Current value: `halloween`.

**`Routes`**: String, *List*: `All routes`, `All Saints' timetable only`. Current value: `All routes`.

**In each data source**, create a calculated field **`Show`**. Analysis → Create Calculated Field, with that source selected:

```
[Feed] = [Saturday]
AND ([Routes] = "All routes" OR [Timetable] = "All Saints' timetable")
```

On **every** sheet below, drag `Show` to **Filters** → tick **True**.

## 3. Sheet "Map" (source: route_lines)

1. Double-click **Geometry**. A map appears.
2. Drag **Route**, **Direction Id** and **Shape Id** onto **Detail**, so each route variant is its own line.
3. Drag **Mode Group** onto **Color** → click Color → **Edit Colors** → set each mode to the hex values in the table above.
4. Drag **Mode Group** onto **Size** too → click the size legend → **Edit Sizes** → *Reversed* if needed. You want Bus thinnest. Then drag the slider until bus lines are hairline and rail lines are clearly thicker. Hide the size legend (right-click → Hide Card).
5. Color → **Opacity 85%**, Border **None**.
6. **Draw order:** in the colour legend, drag the items so **Bus** is drawn underneath the rail lines. If buses cover trams after a reorder, reverse it.
7. **Map → Background Maps → Light**, then **Map → Map Layers → Washout 40%**. Untick everything except *Base*, *Land Cover*, *Coastlines*, *Streets & Highways* and *Water labels*.
8. **Map → Map Options**: untick *Show Map Search*. Keep zoom controls.
9. **Tooltip** (click Tooltip on the Marks card) → replace the text with:
   ```
   <Route>   (Tableau Semibold 11)
   <Mode Group> · <Timetable>
   <SUM(Departures)> departures on this variant in the window
   ```
10. Rename the sheet **Map**.

## 4. Sheet "Hourly" (source: hourly)

1. Drag **Hour** to **Columns** → right-click the pill → **Exact Date**, then **Continuous** (green).
2. Drag **Departures** to **Rows**. Set Marks type to **Bar**.
3. **Mode Group** → **Color** → same hex values as the map. In the legend, order it **Bus at the bottom** of the stack (drag it; check the bars).
4. Color → **Border: `#FCFCFB`**. This leaves a thin background-coloured gap between stacked segments.
5. **Size**: drag the slider so the bars are about 80% of their hour slot, with visible gaps between bars.
6. **X axis**: right-click → Edit Axis → Tick marks *Fixed*, every **3 hours**. Format → Dates → *Custom* `ddd HH:mm`. Clear the axis title.
7. **Y axis**: title `Departures per hour`, Tableau Book 9, muted.
8. **Format → Lines**: Grid lines (Rows) thin `#EBEAE6`. Columns: none. Zero line: thin `#8A8984`. **Format → Borders**: all *None*.
9. **Tooltip:**
   ```
   <Hour formatted as ddd HH:mm> · <Mode Group>
   <SUM(Departures)> planned departures
   ```
10. Rename the sheet **Hourly**.

## 5. BAN sheets (source: hourly)

Make three small sheets. For each one, drag the measure to **Text**, then click Text → … to edit:

| Sheet | Measure | Text |
|---|---|---|
| BAN departures | `SUM(Departures)` | number, then a new line: `planned departures` |
| BAN routes | `COUNTD(Route)` | `routes running` |
| BAN holiday | calc `COUNTD(IF [Timetable] = "All Saints' timetable" THEN [Route] END)` | `routes on All Saints' timetable` |

Use the BAN number and label fonts from the design section, aligned left. Format the number with a thousands separator: right-click → Format → Numbers → Number (Custom), 0 decimals.

## 6. Dashboard

1. **New Dashboard** → Size **Fixed 1200 × 820**.
2. **Format → Dashboard**: shading `#FCFCFB`. Set each worksheet's shading to *None* so the background shows through.
3. Drag in a **Vertical** container. Inside it, from top to bottom:
   - **Header**, a horizontal container holding:
     - a **Text** object:
       - Line 1: `Halloween on HSL` (title font)
       - Line 2: `Planned departures, Saturday 00:00 → Sunday 04:00 · All Saints' Day moved 11 routes to a holiday timetable` (subtitle font)
     - the two parameter controls on the right (right-click a sheet → Parameters → show both; set them to *Compact list*).
   - **Body**, a horizontal container: **Map** on the left (about 60%), then a vertical container on the right with the 3 BANs side by side on top and **Hourly** below. Move the mode legend under Hourly and set it to *single row*, with no title.
   - **Footer** text, muted 9: `Data: HSL GTFS via Mobility Database (CC BY 4.0) · Planned timetable, direct routes only · Observed delays: coming next`.
4. Hide all sheet titles (right-click → *Hide title*). The header and axis titles already explain them.
5. Padding: 16 px outer, 8 px between items. Layout tab → Inner/Outer padding.

## 7. Interaction

**Dashboard → Actions → Add Action → Filter**:
- Source: **Map**, run on **Select**.
- Targets: **Hourly**, **BAN departures**, **BAN routes**, **BAN holiday**.
- Target filters: **Selected fields** → **Route (route_lines) → Route (hourly)**.
- Clearing the selection will: **Show all values**.

Clicking a route line now filters the chart and the numbers. Clicking empty map space resets them.

## 8. Checks

- BAN departures = **511,897** (Halloween) / **511,709** (ordinary Saturday).
- Hover the Sat 18:00 bar → total **28,242**.
- BAN routes = **266**. Routes → *All Saints' timetable only* → **11** routes: Bus 24, 24X, 25, 37, 41, 42, Ferry 19, Train U, Tram 13, 13H, H.
- Click Tram 13H on the map → the chart shows only its departures.

## 9. Save

**File → Save to Tableau Public As…** (free account). The workbook is public, which is fine: HSL data is CC BY 4.0. Copy the URL into `docs/sources.md`.
