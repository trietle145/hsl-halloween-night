-- Service dates to analyse, and which feed (schema) to take each one from.
DROP TABLE IF EXISTS public.study_dates;
CREATE TABLE public.study_dates (service_date date PRIMARY KEY, feed text NOT NULL, label text NOT NULL);
INSERT INTO public.study_dates VALUES
  ('2026-10-30', 'halloween', 'Fri before Halloween (covers Sat 00:00-04:30)'),
  ('2026-10-31', 'halloween', 'Halloween / All Saints'' Day'),
  ('2026-11-01', 'halloween', 'Sun (covers the end of Sat night)'),
  ('2026-10-16', 'baseline',  'Fri before baseline Saturday'),
  ('2026-10-17', 'baseline',  'Baseline Saturday'),
  ('2026-10-18', 'baseline',  'Sun after baseline Saturday');
