--essentially picking the 28 hours to look at (halloween and baseline)
DROP TABLE IF EXISTS departures;
CREATE TABLE departures AS
--create the 1day4hour window(for saturday + nightout to consider)
WITH study_window AS (
  SELECT service_date::timestamp AS window_start,
         service_date + interval '1 day 4 hours' AS window_end
  FROM public.study_dates
  WHERE feed = current_schema() AND extract(isodow FROM service_date) = 6
)
SELECT a.service_date,
       -- GTFS times can pass 24:00 (25:30 = 01:30 next day); adding as an interval handles that.
       -- Only safe because neither window has a clock change (24-25 Oct would break it).
       a.service_date + st.departure_time::interval AS departure_ts,
       st.stop_id,
       r.route_id,
       r.route_short_name AS route,
       CASE WHEN r.route_type = '0' THEN 'tram'
            WHEN r.route_type = '1' THEN 'metro'
            WHEN r.route_type = '4' THEN 'ferry'
            WHEN r.route_type = '109' THEN 'train'
            WHEN r.route_type = '900' THEN 'light rail'
            ELSE 'bus' END AS mode,
       t.direction_id,
       t.trip_id,
       a.service_id
FROM active_services a
JOIN trips t ON t.service_id = a.service_id
JOIN stop_times st ON st.trip_id = t.trip_id
JOIN routes r ON r.route_id = t.route_id
CROSS JOIN study_window w
WHERE st.pickup_type <> '1'  --last stop of a trip: arrival only, nobody can board
  AND a.service_date + st.departure_time::interval >= w.window_start
  AND a.service_date + st.departure_time::interval <  w.window_end;

CREATE INDEX ON departures (stop_id, departure_ts);
