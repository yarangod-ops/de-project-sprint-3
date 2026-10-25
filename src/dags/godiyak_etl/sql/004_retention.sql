DELETE FROM mart.f_customer_retention WHERE week_start=ANY(%(weeks)s::date[]);
WITH per_customer AS (
 SELECT date_trunc('week',c.date_actual)::date AS week_start,f.item_id,f.customer_id,
 count(*) FILTER(WHERE f.status='shipped') AS purchases,
 count(*) FILTER(WHERE f.status='refunded') AS refunds,
 coalesce(sum(f.payment_amount) FILTER(WHERE f.status='shipped'),0) AS shipped_revenue
 FROM mart.f_sales f JOIN mart.d_calendar c ON c.date_id=f.date_id
 WHERE date_trunc('week',c.date_actual)::date=ANY(%(weeks)s::date[])
 GROUP BY date_trunc('week',c.date_actual)::date,f.item_id,f.customer_id
)
INSERT INTO mart.f_customer_retention(new_customers_count,returning_customers_count,
 refunded_customer_count,period_name,period_id,item_id,new_customers_revenue,
 returning_customers_revenue,customers_refunded,week_start)
SELECT count(*) FILTER(WHERE purchases=1),count(*) FILTER(WHERE purchases>1),
 count(*) FILTER(WHERE refunds>0),'weekly',extract(week FROM week_start)::integer,item_id,
 coalesce(sum(shipped_revenue) FILTER(WHERE purchases=1),0),
 coalesce(sum(shipped_revenue) FILTER(WHERE purchases>1),0),sum(refunds),week_start
FROM per_customer GROUP BY week_start,item_id;
