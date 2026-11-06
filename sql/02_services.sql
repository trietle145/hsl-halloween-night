DROP TABLE IF EXISTS active_services;
CREATE TABLE active_services AS
  SELECT d.service_date, c.service_id FROM public.study_dates d
  JOIN calendar c ON to_char(d.service_date, 'YYYYMMDD') BETWEEN c.start_date AND c.end_date
   AND CASE extract(isodow FROM d.service_date)
         WHEN 1 THEN c.monday WHEN 2 THEN c.tuesday WHEN 3 THEN c.wednesday
         WHEN 4 THEN c.thursday WHEN 5 THEN c.friday WHEN 6 THEN c.saturday
         ELSE c.sunday END = '1'
  WHERE d.feed = current_schema()
EXCEPT
  SELECT d.service_date, cd.service_id FROM public.study_dates d
  JOIN calendar_dates cd ON cd.date = to_char(d.service_date, 'YYYYMMDD') AND cd.exception_type = '2'
  WHERE d.feed = current_schema() --remove type 2 days
UNION
  SELECT d.service_date, cd.service_id FROM public.study_dates d
  JOIN calendar_dates cd ON cd.date = to_char(d.service_date, 'YYYYMMDD') AND cd.exception_type = '1'
  WHERE d.feed = current_schema() --add type 1 days
;
-- the gtfs zip have exceptions lol(2csv: calendar, exceptions)