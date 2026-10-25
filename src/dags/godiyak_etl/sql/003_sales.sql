DELETE FROM mart.f_sales f USING mart.d_calendar c
WHERE f.date_id=c.date_id AND c.date_actual=ANY(%(days)s::date[]);
INSERT INTO mart.f_sales(date_id,item_id,customer_id,city_id,quantity,payment_amount,status,source_uniq_id)
SELECT c.date_id,u.item_id,u.customer_id,u.city_id,
 CASE WHEN u.status='refunded' THEN -abs(u.quantity) ELSE abs(u.quantity) END,
 CASE WHEN u.status='refunded' THEN -abs(u.payment_amount) ELSE abs(u.payment_amount) END,
 u.status,u.uniq_id
FROM staging.user_order_log u JOIN mart.d_calendar c ON c.date_actual=u.date_time::date
WHERE u.date_time::date=ANY(%(days)s::date[]);
-- Покупка и возврат остаются отдельными операциями.
