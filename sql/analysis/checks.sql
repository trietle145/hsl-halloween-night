-- reliability checks across both feeds: run by hand (psql -f), not by load_observed.py

-- 4. Halloween minus ordinary Saturday, per hour x mode (night hours)
SELECT window_hour, mode_group,
       h.n_observed AS n_hal, b.n_observed AS n_base,
       h.pct_late AS late_hal, b.pct_late AS late_base, h.pct_late - b.pct_late AS late_diff,
       h.median_delay_s - b.median_delay_s AS median_diff_s,
       h.pct_observed AS obs_hal, b.pct_observed AS obs_base,
       h.low_n OR b.low_n AS low_n
FROM halloween.reliability h
JOIN baseline.reliability b USING (window_hour, mode_group)
WHERE window_hour >= 18
ORDER BY mode_group, window_hour;

-- 5a. after midnight (window_hour >= 24), per terminal, both feeds
CREATE TEMP VIEW night_terminal AS
SELECT terminal_id, s.stop_name,
       count(*) FILTER (WHERE h) AS n_hal, count(*) FILTER (WHERE NOT h) AS n_base,
       round(100.0 * avg((delay_s > 180)::int) FILTER (WHERE h), 1) AS late_hal,
       round(100.0 * avg((delay_s > 180)::int) FILTER (WHERE NOT h), 1) AS late_base
FROM (SELECT true AS h, terminal_id, delay_s FROM halloween.reliability_base WHERE window_hour >= 24 AND is_observed
      UNION ALL
      SELECT false, terminal_id, delay_s FROM baseline.reliability_base WHERE window_hour >= 24 AND is_observed) x
JOIN halloween.stops s ON s.stop_id = x.terminal_id
GROUP BY 1, 2;

SELECT *, late_hal - late_base AS diff FROM night_terminal
WHERE n_hal >= 30 AND n_base >= 30 ORDER BY diff DESC;

-- 5b. how many terminals got worse (n >= 30 both nights)
SELECT count(*) AS terminals, count(*) FILTER (WHERE late_hal > late_base) AS worse,
       count(*) FILTER (WHERE late_hal - late_base > 5) AS worse_by_5pp
FROM night_terminal WHERE n_hal >= 30 AND n_base >= 30;

-- 5c. network after midnight: all terminals vs without the top 2 by n_hal
WITH top2 AS (SELECT terminal_id FROM night_terminal ORDER BY n_hal DESC LIMIT 2)
SELECT 'all terminals' AS scope,
       round(sum(n_hal * late_hal) / sum(n_hal), 1) AS late_hal,
       round(sum(n_base * late_base) / sum(n_base), 1) AS late_base
FROM night_terminal
UNION ALL
SELECT 'without top 2 (' || string_agg(stop_name, ', ') || ')', NULL, NULL FROM night_terminal WHERE terminal_id IN (SELECT terminal_id FROM top2)
UNION ALL
SELECT 'without top 2',
       round(sum(n_hal * late_hal) / sum(n_hal), 1),
       round(sum(n_base * late_base) / sum(n_base), 1)
FROM night_terminal WHERE terminal_id NOT IN (SELECT terminal_id FROM top2);

-- 6. coverage: planned vs observed after midnight, per feed, buses; and Hakaniemi
SELECT 'halloween' AS feed, terminal_id = '1000012' AS hakaniemi, count(*) planned, count(*) FILTER (WHERE is_observed) observed,
       round(100.0 * avg(is_observed::int), 1) pct_obs
FROM halloween.reliability_base WHERE window_hour >= 24 AND mode_group = 'Bus' GROUP BY 1, 2
UNION ALL
SELECT 'baseline', terminal_id = '1000012', count(*), count(*) FILTER (WHERE is_observed), round(100.0 * avg(is_observed::int), 1)
FROM baseline.reliability_base WHERE window_hour >= 24 AND mode_group = 'Bus' GROUP BY 1, 2 ORDER BY 2, 1;

-- 7. daytime vs evening vs night, buses, both feeds
SELECT CASE WHEN window_hour < 6 THEN '1 early (00-06)' WHEN window_hour < 18 THEN '2 day (06-18)'
            WHEN window_hour < 24 THEN '3 evening (18-24)' ELSE '4 night (24-28)' END AS part,
       sum(h.n_observed) n_hal, sum(b.n_observed) n_base,
       round(sum(h.n_observed * h.pct_late) / sum(h.n_observed), 1) late_hal,
       round(sum(b.n_observed * b.pct_late) / sum(b.n_observed), 1) late_base
FROM halloween.reliability h JOIN baseline.reliability b USING (window_hour, mode_group)
WHERE mode_group = 'Bus' GROUP BY 1 ORDER BY 1;
