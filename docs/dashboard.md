# Dashboard build guide: "Halloween night" (observed reliability)

The second dashboard in the same workbook (`tableau/hsl.twb`). The first one shows that the planned timetable didn't change. This one shows what actually ran.

Data: `data/exports/hsl_reliability.csv`. Rebuild it with:

```
python src/load_observed.py
python src/export.py
```

> **Tableau cache:** this is a **new** file, so add it as a **new data source**. Don't swap it into an existing source: Tableau Public remembers CSV column layouts.

> Weather is ruled out: both nights were dry (FMI). The footer says so, because it's the first thing a reader will ask.

---

## The story in one screen

| Question | Where the reader finds it | Answer |
|---|---|---|
| Was Halloween night worse? | Two big numbers, top left | **36%** of night buses > 3 min late, vs **13%** on an ordinary Saturday |
| When did it start? | Line chart | Slightly worse all evening, then it jumps at midnight |
| Everywhere, or one place? | Map | 12 of 13 big terminals are worse (red) |

---

## Design

**Layout** (fixed 1200 × 820, same as the first dashboard):

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Halloween night on HSL                                       [Mode: Bus ▾] │ header
│ Same timetable as an ordinary Saturday, but after midnight buses ran       │
│ late almost three times as often                                           │
├──────────────────────────────────────┬─────────────────────────────────────┤
│  36%            13%           12/13  │                                     │ BANs
│  Halloween      ordinary      big    │                                     │
│  night          Saturday      terminals                                    │
│  > 3 min late   night         worse  │            TERMINAL MAP             │
├──────────────────────────────────────┤      dot = terminal, size = n       │
│  % departures > 3 min late, by hour  │      colour = change after midnight │
│                          ░░░░░░░░░   │      (blue better · grey same ·     │
│                          ░ after ░   │       red worse)                    │
│              Halloween ╱‾‾░midnight░ │                                     │
│  ___________________╱    ░░░░░░░░░   │                                     │
│  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾ Ordinary   │      ■ -40 pp ─── 0 ─── +40 pp ■    │
│  Sat 00  06   12   18   Sun 00  04   │                                     │
├──────────────────────────────────────┴─────────────────────────────────────┤
│ Observed departures from 122 terminals (Reittiloki) · coverage note · data │ footer
└────────────────────────────────────────────────────────────────────────────┘
```

Reading order runs left to right: the numbers give the claim, the line shows when it happened, and the map shows where. **Click a terminal** and the numbers and the line switch to that terminal.

**Colours.** The palette was checked with the dataviz validator (colour-blind separation, contrast). **On this dashboard, colour means "which Saturday", not mode.** The mode colours belong to the first dashboard.

| Role | Hex | Notes |
|---|---|---|
| Background | `#FCFCFB` | same as dashboard 1 |
| Text, primary | `#0B0B0B` | |
| Text, secondary | `#52514E` | |
| Text, muted / axes | `#898781` | |
| Grid lines | `#E1E0D9` | hairline |
| **Halloween** (line, BAN) | `#EB6834` | warm = Halloween |
| **Ordinary Saturday** (line, BAN) | `#2A78D6` | cool = ordinary |
| After-midnight band | `#F0EFEC` | neutral, sits behind the lines |
| Map: worse (+) | `#E34948` | diverging, red pole |
| Map: better (−) | `#2A78D6` | diverging, blue pole |
| Map dot outline | `#898781` | keeps near-zero (pale) dots visible on the basemap |

The warm/cool logic carries across the whole dashboard: orange line = Halloween, red dot = Halloween was worse there. Readers learn it once.

**Fonts** (same as dashboard 1, Tableau's own fonts):
- Title: Tableau Semibold 20, primary
- Subtitle: Tableau Book 12, secondary
- BAN number: Tableau Semibold 32, in the series colour (see the BAN step)
- BAN label: Tableau Book 9, secondary, 3 short lines
- Axes, legends, footer: Tableau Book 9, muted

**Rules:** one y-axis (no dual axis). No number on every point: the two line ends are labelled and the tooltips carry the rest. The grid is a hairline with no borders. Every big number says what it counts.

---

## 1. Data source

1. **Data → New Data Source → Text file → `hsl_reliability.csv`**.
2. On the Data Source page, check the field types:

| Field | Type it should be |
|---|---|
| `Window Time` | **Date & time** (calendar-clock icon). It's a fake date: 1 Jan 2000 was a Saturday, so both Saturdays share one Sat 00:00 → Sun 04:00 axis. |
| `Lat`, `Lon` | Number → right-click → **Geographic Role → Latitude / Longitude** |
| `Window Hour`, `N *`, `Real Cancels` | Number (#) |
| `Terminal Id` | **String** (Abc). If it shows as #, change it, so ids aren't summed. |

3. Rename the data source **Reliability**.

## 2. Calculated fields

Analysis → Create Calculated Field. Make all of these first, then build the sheets.

**`Saturday`**: the series name readers see.
```
IF [Feed] = "halloween" THEN "Halloween · 31 Oct" ELSE "Ordinary Saturday · 17 Oct" END
```

**`% Late`**: always computed from the sums. Never average percentages.
```
SUM([N Late]) / SUM([N Observed])
```
Format: Percentage, 0 decimals.

**`Late Halloween`** and **`Late Ordinary`** (for the BANs and the map):
```
SUM(IF [Feed] = "halloween" THEN [N Late] END) / SUM(IF [Feed] = "halloween" THEN [N Observed] END)
```
```
SUM(IF [Feed] = "baseline" THEN [N Late] END) / SUM(IF [Feed] = "baseline" THEN [N Observed] END)
```
Format both: Percentage, 0 decimals.

**`Change (pp)`**: percentage points, Halloween minus ordinary.
```
([Late Halloween] - [Late Ordinary]) * 100
```
Format: Number (Custom) `+0.0" pp";-0.0" pp";0" pp"`.

**`Enough Data`**: hides terminals with too few departures to trust.
```
SUM(IF [Feed] = "halloween" THEN [N Observed] END) >= 30
AND SUM(IF [Feed] = "baseline" THEN [N Observed] END) >= 30
```

**`Coverage Halloween`** and **`Coverage Ordinary`** (for tooltips):
```
SUM(IF [Feed] = "halloween" THEN [N Observed] END) / SUM(IF [Feed] = "halloween" THEN [N Planned] END)
```
```
SUM(IF [Feed] = "baseline" THEN [N Observed] END) / SUM(IF [Feed] = "baseline" THEN [N Planned] END)
```

## 3. Sheet "Late by hour" (line chart)

1. **Window Time** → Columns → right-click → **Exact Date**, then **Continuous** (green).
2. **% Late** → Rows. Marks type: **Line**.
3. **Saturday** → Color → Edit Colors: Halloween `#EB6834`, Ordinary `#2A78D6`.
4. Size: drag the slider to about the 2nd notch, so the lines are thin (about 2 px).
5. **Mode Group** → Filters → select **Bus** only → right-click the filter → **Show Filter**. On the filter card: ▾ → **Single Value (dropdown)**, and ▾ → **Apply to Worksheets → All Using This Data Source**.
6. **Direct labels**: drag **Saturday** to Label as well. Click Label → *Label line ends*, font Tableau Book 9. Click the text "…" and set it to `<Saturday>`, plus `<% Late>` on a new line. Then **hide the colour legend**: the labelled line ends replace it, and the mode filter is enough chrome. (The dataviz rule is a legend *or* direct labels when there are ≤ 4 series. Two labelled lines read faster.)
7. **After-midnight band**: Analytics pane → drag **Reference Band** onto the chart → *Table*, on **Window Time**.
   - Band from: Constant `2/1/2000 00:00` (Sun 00:00). Band to: Constant `2/1/2000 04:00`. The date format follows your Tableau locale, so pick it from the date picker.
   - Fill `#F0EFEC`, no line. Label: Custom `after midnight`, Tableau Book 9, muted, top.
   - Right-click the band → **Format → move to back**, if the lines don't draw on top.
8. **X axis**: right-click → Edit Axis → Tick marks *Fixed*, every **6 hours**, starting `1/1/2000 00:00`. Format → Dates → Custom `ddd HH:mm`, which shows *Sat 18:00*, *Sun 00:00*. Clear the axis title.
9. **Y axis**: Edit Axis → *Include zero*, fixed start 0. Title `% departures > 3 min late`. Ticks Tableau Book 9, muted.
10. **Format → Lines**: Rows grid lines thin `#E1E0D9`. Columns: none. Zero line `#C3C2B7`. **Format → Borders**: all *None*.
11. **Tooltip**:
    ```
    <Saturday>                                  (Tableau Semibold 10)
    <WINDOW_TIME formatted ddd HH:mm>
    <% Late> late (> 3 min) · <SUM(N Observed)> observed departures
    ```
12. Rename the sheet **Late by hour**.

## 4. Sheet "Terminal map"

1. Double-click **Lon**, then **Lat** (Tableau puts AVG(Lon) in Columns and AVG(Lat) in Rows and draws a map).
2. **Terminal Id** → Detail and **Terminal** → Detail. That gives one dot per terminal.
3. **Window Hour** → Filters → *All values* → Range of values → **At least 24**. This map shows **after midnight only**.
4. **Enough Data** → Filters → **True**. You should see **13 dots** with Mode = Bus.
5. **Change (pp)** → Color → Edit Colors → *Custom Diverging*:
   - Left `#2A78D6`, right `#E34948`.
   - Advanced: **Start −40, End +40, Center 0**. The scale must be symmetric, so that grey honestly means "no change".
   - Leave it *not* stepped.
6. **SUM(N Observed)** → Size. Use a small range, so the biggest dot (Hakaniemi) doesn't swamp the map. Hide the size legend (right-click → Hide Card).
7. Color → Opacity **90%**, Border `#898781`.
8. **Map → Background Maps → Light**, **Map Layers → Washout 50%**. Keep only *Base*, *Land Cover*, *Coastlines*, *Streets & Highways* and *Water labels*. **Map Options**: untick *Show Map Search*.
9. Zoom to the area Espoo ↔ Vantaa airport ↔ Kontula, then **Map → Lock pan & zoom**, so a click doesn't move the view.
10. Colour legend: title `Change in % late after midnight`, Tableau Book 9. It should sit at the bottom of the map.
11. **Tooltip**:
    ```
    <Terminal>                                   (Tableau Semibold 10)
    After midnight, > 3 min late
    Halloween <Late Halloween> · Ordinary <Late Ordinary>   (<Change (pp)>)
    Observed: Halloween <Coverage Halloween> · Ordinary <Coverage Ordinary>
    Click to see this terminal's hours
    ```
    The coverage line matters for **Hakaniemi**: only 43% of its departures were observed on the ordinary night, and the tooltip makes that visible.
12. Rename the sheet **Terminal map**.

## 5. BAN sheets

Three small sheets. On each one, add a **Window Hour** filter of **at least 24**, because the numbers are about after midnight. The Mode filter already applies to them.

| Sheet | Text card | Number colour | Label (3 lines) |
|---|---|---|---|
| BAN Halloween | `Late Halloween` | `#EB6834` | `Halloween night` / `departures > 3 min late` / `Sun 00:00–04:00` |
| BAN Ordinary | `Late Ordinary` | `#2A78D6` | `Ordinary Saturday` / `night, same hours` / `(17–18 Oct)` |
| BAN Terminals | text object (not a sheet) | primary `#0B0B0B` | `12 / 13` then `big terminals worse` / `(≥ 30 departures both nights)` |

For each sheet: drag the field to **Text**. Click Text → "…" → number in Tableau Semibold 32 in the colour above, then the label lines in Tableau Book 9, secondary. Align left. Format → Shading *None*.

The number takes the series colour because it *is* that series: it ties the BAN to its line below. The labels stay in text ink (the dataviz rule: text never wears the series colour, except the number that stands for the series).

The `12 / 13` comes from `sql/analysis/checks.sql` (query 5b). If the data changes, re-run the query and update the text.

## 6. Dashboard

1. **New Dashboard** → name it **Halloween night** → Size **Fixed 1200 × 820**.
2. **Format → Dashboard**: shading `#FCFCFB`. Set each sheet's shading to *None*.
3. A **Vertical** container holds:
   - **Header**: a horizontal container.
     - **Text** on the left:
       - Line 1: `Halloween night on HSL` (title)
       - Line 2: `Same timetable as an ordinary Saturday, but after midnight buses ran late almost three times as often` (subtitle)
     - The **Mode Group** filter card on the right, as a compact dropdown with the title `Mode`.
   - **Body**: a horizontal container.
     - **Left (about 45%)**: a vertical container with the BAN row on top (BAN Halloween, BAN Ordinary, BAN Terminals text side by side, about 120 px tall), then **Late by hour** below.
     - **Right (about 55%)**: **Terminal map**, with its colour legend floating bottom-left inside the map, or tiled under it.
   - **Footer** text (muted, Tableau Book 9, 2 lines):
     `Observed departures from HSL's 122 bus/metro/train terminals (Reittiloki), compared with the GTFS timetable · trams and most mid-route stops aren't covered · late = left > 3 min after the timetable`
     `Coverage: 95% of night bus departures observed on Halloween, 84% on the ordinary Saturday (Hakaniemi 43%) · Both nights dry (FMI) · Data: HSL via Reittiloki and Mobility Database, FMI, CC BY 4.0`
4. Hide all sheet titles. The header, the BAN labels and the axis titles explain everything.
5. Padding: 16 px outer, 8 px between items, and **24 px** between the left column and the map, so the two halves breathe.

## 7. Interaction

**Dashboard → Actions → Add Action → Filter**:
- Name: `Pick a terminal`
- Source: **Terminal map**, run on **Select**
- Targets: **Late by hour**, **BAN Halloween**, **BAN Ordinary**
- Target filters: Selected fields → **Terminal Id**
- Clearing the selection will: **Show all values**

Click Hakaniemi and the line and numbers show only Hakaniemi. Click empty map space to go back to the whole network.

**Optional: highlight on hover.** Add a Highlight action from **Late by hour** on Hover with the field **Saturday**. Hovering one line dims the other.

## 8. Checks

With Mode = **Bus** and nothing selected:

| What | Expected |
|---|---|
| BAN Halloween | **36%** (35.9%) |
| BAN Ordinary | **13%** (13.0%) |
| Line, Sun 00:00 point | Halloween **34%**, Ordinary **13%** |
| Map dots | **13** |
| Westendinasema tooltip | 63% vs 23% (**+40.0 pp**), the reddest dot |
| Lentoasema tooltip | 17% vs 17% (**0 pp**), grey |
| Click Rautatientori | BANs **15%** / **3%** |
| Mode = Metro | Line drops to near 0. Metro has no night service, so the BANs go blank or show 0, and that's expected. |

All of these come from `data/exports/hsl_reliability.csv` (checked with Python) and `sql/analysis/checks.sql`.

## 9. After building

- **Dashboard 1 still works:** its data sources didn't change.
- **Order the two dashboards** in the workbook: *planned* first, then *Halloween night*. Optional: put them in a **Story** (New Story) with two points, "The timetable didn't change" → "But the buses did". This is what the final project review checks for.
- Save: **File → Save to Tableau Public As…** (the same workbook).
