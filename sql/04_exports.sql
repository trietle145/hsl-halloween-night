-- Small Tableau-ready views; src/export.py dumps them for each feed
CREATE OR REPLACE VIEW route_info AS
SELECT route_id,
       initcap(min(mode)) || ' ' || min(route) AS route_label,
       CASE min(mode) WHEN 'bus' THEN 'Bus' WHEN 'metro' THEN 'Metro' WHEN 'train' THEN 'Train'
                      WHEN 'ferry' THEN 'Ferry' ELSE 'Tram & light rail' END AS mode_group,
       CASE WHEN bool_or(service_id LIKE '%\_PY') THEN 'All Saints'' timetable' ELSE 'Regular' END AS timetable
FROM departures
GROUP BY route_id;

-- window_hour 0-27 (0 = Sat 00:00, 24 = Sun 00:00) puts both Saturdays on one axis
CREATE OR REPLACE VIEW export_hourly AS
SELECT date_trunc('hour', d.departure_ts) AS hour,
       (extract(epoch FROM date_trunc('hour', d.departure_ts) - w.sat) / 3600)::int AS window_hour,
       r.mode_group, r.timetable, r.route_label AS route, count(*) AS departures
FROM departures d
JOIN route_info r USING (route_id)
-- not current_schema(): in a view it's evaluated at query time, not when the view is created
CROSS JOIN (SELECT date_trunc('day', min(departure_ts)) AS sat FROM departures) w
GROUP BY 1, 2, 3, 4, 5;

CREATE OR REPLACE VIEW export_stop_routes AS
SELECT d.stop_id, s.stop_name, s.stop_lat::float AS lat, s.stop_lon::float AS lon,
       r.mode_group, r.route_label AS route, count(*) AS departures
FROM departures d
JOIN stops s ON s.stop_id = d.stop_id
JOIN route_info r USING (route_id)
GROUP BY 1, 2, 3, 4, 5, 6;

-- one simplified line per route variant; ~5 m tolerance keeps the GeoJSON small
CREATE OR REPLACE VIEW export_route_lines AS
SELECT r.route_label AS route, r.mode_group, r.timetable, d.direction_id, t.shape_id, count(*) AS departures,
       ST_AsGeoJSON(ST_Simplify(l.geom, 0.00005), 6) AS geojson
FROM departures d
JOIN route_info r USING (route_id)
JOIN trips t ON t.trip_id = d.trip_id
JOIN shape_lines l ON l.shape_id = t.shape_id
GROUP BY 1, 2, 3, 4, 5, l.geom;
