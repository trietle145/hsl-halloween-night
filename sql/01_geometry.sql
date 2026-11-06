-- Runs inside the schema set by build_db.py (search_path = <schema>, public).

CREATE INDEX ON stop_times (trip_id);
CREATE INDEX ON stop_times (stop_id);
CREATE INDEX ON trips (trip_id);
CREATE INDEX ON trips (service_id);

-- stops as points (WGS84 lon/lat)
ALTER TABLE stops ADD COLUMN geom geometry(Point, 4326);
UPDATE stops SET geom = ST_SetSRID(ST_MakePoint(stop_lon::float, stop_lat::float), 4326);

-- one line per shape, points joined in sequence order
CREATE TABLE shape_lines AS
SELECT shape_id,
       ST_MakeLine(ST_SetSRID(ST_MakePoint(shape_pt_lon::float, shape_pt_lat::float), 4326)
                   ORDER BY shape_pt_sequence::int) AS geom
FROM shapes
GROUP BY shape_id;
