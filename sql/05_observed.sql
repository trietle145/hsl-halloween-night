DROP TABLE IF EXISTS observed_departures;
CREATE TABLE observed_departures AS
-- same 28 h window as 03_departures.sql
WITH study_window AS (
  SELECT service_date::timestamp AS window_start,
         service_date + interval '1 day 4 hours' AS window_end
  FROM public.study_dates
  WHERE feed = current_schema() AND extract(isodow FROM service_date) = 6
),
obs AS (
  -- duplicates
  SELECT DISTINCT ON (o.stop_id, o.route_id, o.direction, o.planned_ts)
         o.*,
         count(*) OVER (PARTITION BY o.stop_id, o.route_id, o.direction, o.planned_ts) AS n_vehicles
  FROM public.observed o
  WHERE o.feed = current_schema()
  ORDER BY o.stop_id, o.route_id, o.direction, o.planned_ts, o.observed_ts IS NULL, o.observed_ts
)
-- a trip can pass two platforms of one terminal in the same minute (Kontula 92N); keep the exact-stop match
SELECT DISTINCT ON (o.stop_id, o.route_id, o.direction, o.planned_ts)
       o.terminal_id,
       o.service_date,
       o.stop_id,
       o.route_id,
       o.direction,
       -- Reittiloki times carry an offset (+03 baseline, +02 Halloween); departures uses plain local time
       o.planned_ts AT TIME ZONE 'Europe/Helsinki' AS planned_ts,
       o.observed_ts AT TIME ZONE 'Europe/Helsinki' AS observed_ts,
       (o.observed_ts IS NOT NULL) AS is_observed,
       o.delay_s,
       -- real = flagged cancelled and some reason other than TIS_ERROR (data errors);
       o.is_cancelled AND coalesce('TIS_ERROR' <> ANY(o.cancellation_types), false) AS real_cancel,
       o.cancellation_types,
       o.n_vehicles,
       d.trip_id IS NOT NULL AS matched,  -- false: no planned GTFS departure (U-lines, arrival-only terminal stops)
       d.stop_id <> o.stop_id AS stop_moved,  -- matched at another platform of the same terminal
       d.trip_id,
       d.mode,
       d.route
FROM obs o
CROSS JOIN study_window w
LEFT JOIN (departures d JOIN stops s ON s.stop_id = d.stop_id)
  -- match on terminal, not stop: platforms move (Hakaniemi baseline: 1111112 vs 1111142)
  ON s.parent_station = o.terminal_id
 AND d.route_id = split_part(o.route_id, ' ', 1)  -- metro is '31M1 7' in Reittiloki, '31M1' in GTFS
 AND d.direction_id = (o.direction - 1)::text     -- Reittiloki 1/2 = GTFS 0/1 (checked: no cross matches)
 AND d.departure_ts = o.planned_ts AT TIME ZONE 'Europe/Helsinki'
WHERE o.planned_ts AT TIME ZONE 'Europe/Helsinki' >= w.window_start
  AND o.planned_ts AT TIME ZONE 'Europe/Helsinki' <  w.window_end
ORDER BY o.stop_id, o.route_id, o.direction, o.planned_ts, d.stop_id = o.stop_id DESC;
