INSERT INTO mart.d_calendar(date_id,date_actual,day_num,month_num,month_actual,month_name,
 year_num,year_actual,week_of_year,week_of_year_iso,epoch,day_suffix,day_name,day_of_week,
 day_of_month,day_of_quarter,day_of_year,week_of_month,month_name_abbreviated,quarter_actual,
 quarter_name,first_day_of_week,last_day_of_week,first_day_of_month,last_day_of_month,
 first_day_of_quarter,last_day_of_quarter,first_day_of_year,last_day_of_year,mmyyyy,mmddyyyy,weekend_indr)
SELECT to_char(d,'YYYYMMDD')::integer,d,extract(day FROM d),extract(month FROM d),
 extract(month FROM d),to_char(d,'FMMonth'),extract(year FROM d),extract(year FROM d),
 extract(week FROM d),to_char(d,'IYYY-"W"IW-ID'),extract(epoch FROM d::timestamp)::bigint,
 to_char(d,'FMDDth'),to_char(d,'FMDay'),extract(isodow FROM d),extract(day FROM d),
 d-date_trunc('quarter',d)::date+1,extract(doy FROM d),to_char(d,'W')::integer,
 to_char(d,'Mon'),extract(quarter FROM d),
 CASE extract(quarter FROM d) WHEN 1 THEN 'First' WHEN 2 THEN 'Second' WHEN 3 THEN 'Third' ELSE 'Fourth' END,
 date_trunc('week',d)::date,(date_trunc('week',d)+interval '6 days')::date,
 date_trunc('month',d)::date,(date_trunc('month',d)+interval '1 month -1 day')::date,
 date_trunc('quarter',d)::date,(date_trunc('quarter',d)+interval '3 months -1 day')::date,
 date_trunc('year',d)::date,(date_trunc('year',d)+interval '1 year -1 day')::date,
 to_char(d,'MMYYYY'),to_char(d,'MMDDYYYY'),extract(isodow FROM d)>=6
FROM (SELECT DISTINCT date_time::date d FROM staging.user_order_log
      WHERE date_time::date=ANY(%(days)s::date[])) x
WHERE NOT EXISTS(SELECT 1 FROM mart.d_calendar c WHERE c.date_actual=x.d);

INSERT INTO mart.d_item(item_id,item_name)
SELECT DISTINCT ON(item_id) item_id,item_name FROM staging.user_order_log
WHERE date_time::date=ANY(%(days)s::date[]) ORDER BY item_id,date_time DESC,item_name DESC
ON CONFLICT(item_id) DO UPDATE SET item_name=excluded.item_name;
INSERT INTO mart.d_customer(customer_id,first_name,last_name,city_id)
SELECT DISTINCT ON(customer_id) customer_id,first_name,last_name,city_id FROM staging.user_order_log
WHERE date_time::date=ANY(%(days)s::date[]) ORDER BY customer_id,date_time DESC,first_name DESC,last_name DESC
ON CONFLICT(customer_id) DO UPDATE SET first_name=excluded.first_name,last_name=excluded.last_name,city_id=excluded.city_id;
-- UPDATE/INSERT не требуют отдельного UNIQUE по city_id.
UPDATE mart.d_city d SET city_name=s.city_name FROM (
 SELECT DISTINCT ON(city_id) city_id,city_name FROM staging.user_order_log
 WHERE date_time::date=ANY(%(days)s::date[]) ORDER BY city_id,date_time DESC,city_name DESC
) s WHERE d.city_id=s.city_id;
INSERT INTO mart.d_city(city_id,city_name)
SELECT DISTINCT ON(s.city_id) s.city_id,s.city_name FROM staging.user_order_log s
WHERE s.date_time::date=ANY(%(days)s::date[])
 AND NOT EXISTS(SELECT 1 FROM mart.d_city d WHERE d.city_id=s.city_id)
ORDER BY s.city_id,s.date_time DESC,s.city_name DESC;
