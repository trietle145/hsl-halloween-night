-- one row per observed departure, with the shared hour axis and mode group
CREATE OR REPLACE VIEW reliability_base AS
SELECT o.*,
       (extract(epoch FROM date_trunc('hour', o.planned_ts) - w.sat) / 3600)::int AS window_hour,  -- 0 = Sat 00:00, 24 = Sun 00:00
       coalesce(r.mode_group, 'Bus') AS mode_group,  -- unknown to GTFS = U-line 7xxx / 9976 buses
       r.route_label
FROM observed_departures o
LEFT JOIN route_info r ON r.route_id = split_part(o.route_id, ' ', 1)
CROSS JOIN (SELECT date_trunc('day', min(planned_ts)) AS sat FROM observed_departures) w;

CREATE OR REPLACE VIEW reliability AS
SELECT window_hour,
       mode_group,
       count(*) AS n_planned,
       count(*) FILTER (WHERE is_observed) AS n_observed,
       round(100.0 * count(*) FILTER (WHERE is_observed) / count(*), 1) AS pct_observed,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY delay_s)::numeric, 1) AS median_delay_s,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY delay_s)::numeric, 1) AS p90_delay_s,
       round(100.0 * avg((delay_s > 180)::int), 1) AS pct_late, --try to skip nulls, hence avg
       count(*) FILTER (WHERE real_cancel) AS real_cancels,
       count(*) FILTER (WHERE is_observed) < 30 AS low_n
FROM reliability_base
GROUP BY window_hour, mode_group;