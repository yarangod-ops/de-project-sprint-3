-- Миграция сохраняет существующие продажи; её можно запускать повторно.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS etl;
CREATE TABLE IF NOT EXISTS staging.user_order_log (
 id bigserial PRIMARY KEY, uniq_id text NOT NULL, date_time timestamp NOT NULL,
 city_id bigint, city_name text, customer_id bigint NOT NULL, first_name text,
 last_name text, item_id bigint NOT NULL, item_name text, quantity bigint NOT NULL,
 payment_amount numeric(18,2) NOT NULL
);
ALTER TABLE staging.user_order_log ADD COLUMN IF NOT EXISTS status text;
UPDATE staging.user_order_log SET status='shipped' WHERE status IS NULL OR btrim(status)='';
UPDATE staging.user_order_log SET status=lower(btrim(status));
ALTER TABLE staging.user_order_log ALTER COLUMN status SET DEFAULT 'shipped';
ALTER TABLE staging.user_order_log ALTER COLUMN status SET NOT NULL;
-- Заменяем PK(uniq_id) на PK(id): покупка и возврат могут иметь общий uniq_id.
ALTER TABLE staging.user_order_log ADD COLUMN IF NOT EXISTS id bigserial;
DO $$ DECLARE pk record; BEGIN
 FOR pk IN SELECT conname FROM pg_constraint WHERE conrelid='staging.user_order_log'::regclass
   AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (uniq_id)'
 LOOP EXECUTE format('ALTER TABLE staging.user_order_log DROP CONSTRAINT %I',pk.conname); END LOOP;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='staging.user_order_log'::regclass AND contype='p')
 THEN ALTER TABLE staging.user_order_log ADD PRIMARY KEY(id); END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS godiyak_uol_event_idx
 ON staging.user_order_log((date_time::date),uniq_id,status);
CREATE INDEX IF NOT EXISTS godiyak_uol_date_idx ON staging.user_order_log(date_time);

CREATE TABLE IF NOT EXISTS staging.user_activity_log (
 id bigserial PRIMARY KEY, uniq_id text, date_time timestamp NOT NULL,
 action_id bigint NOT NULL, customer_id bigint NOT NULL, quantity bigint NOT NULL
);
ALTER TABLE staging.user_activity_log ADD COLUMN IF NOT EXISTS uniq_id text;
CREATE TABLE IF NOT EXISTS staging.customer_research (
 id bigserial PRIMARY KEY, date_id timestamp NOT NULL, category_id bigint NOT NULL,
 geo_id bigint NOT NULL, sales_qty bigint NOT NULL, sales_amt numeric(18,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS staging.price_log (
 id bigserial PRIMARY KEY, item_name text NOT NULL, price numeric(18,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS mart.d_calendar (
 date_id integer PRIMARY KEY, date_actual date NOT NULL UNIQUE,
 day_num integer, month_num integer, month_actual integer, month_name varchar(20),
 year_num integer, year_actual integer, week_of_year integer, week_of_year_iso varchar(20)
);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_num integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS month_num integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS month_actual integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS month_name varchar(20);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS year_num integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS year_actual integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS week_of_year integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS week_of_year_iso varchar(20);
-- В календаре тренажёра есть дополнительные обязательные поля.
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS epoch bigint;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_suffix varchar(4);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_name varchar(9);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_of_week integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_of_month integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_of_quarter integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS day_of_year integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS week_of_month integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS month_name_abbreviated char(3);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS quarter_actual integer;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS quarter_name varchar(9);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS first_day_of_week date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS last_day_of_week date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS first_day_of_month date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS last_day_of_month date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS first_day_of_quarter date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS last_day_of_quarter date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS first_day_of_year date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS last_day_of_year date;
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS mmyyyy char(6);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS mmddyyyy char(10);
ALTER TABLE mart.d_calendar ADD COLUMN IF NOT EXISTS weekend_indr boolean;
CREATE UNIQUE INDEX IF NOT EXISTS godiyak_calendar_date_idx ON mart.d_calendar(date_actual);
CREATE TABLE IF NOT EXISTS mart.d_item (item_id bigint PRIMARY KEY, item_name text);
CREATE TABLE IF NOT EXISTS mart.d_customer (
 customer_id bigint PRIMARY KEY, first_name text, last_name text, city_id bigint
);
CREATE TABLE IF NOT EXISTS mart.d_city (city_id bigint PRIMARY KEY, city_name text);
CREATE TABLE IF NOT EXISTS mart.f_sales (
 id bigserial PRIMARY KEY, date_id integer NOT NULL, item_id bigint NOT NULL,
 customer_id bigint NOT NULL, city_id bigint, quantity bigint NOT NULL,
 payment_amount numeric(18,2) NOT NULL
);
ALTER TABLE mart.f_sales ADD COLUMN IF NOT EXISTS status text;
-- Прежние строки без статуса считаются покупками.
UPDATE mart.f_sales SET status='shipped' WHERE status IS NULL OR btrim(status)='';
UPDATE mart.f_sales SET status=lower(btrim(status));
ALTER TABLE mart.f_sales ALTER COLUMN status SET DEFAULT 'shipped';
ALTER TABLE mart.f_sales ALTER COLUMN status SET NOT NULL;
ALTER TABLE mart.f_sales ADD COLUMN IF NOT EXISTS source_uniq_id text;
-- Перед сменой типа проверяем, что исторические суммы не потеряют точность.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM mart.f_sales WHERE payment_amount::numeric <> round(payment_amount::numeric,2))
 THEN RAISE EXCEPTION 'f_sales contains historical amounts with more than two decimal places'; END IF;
END $$;
ALTER TABLE mart.f_sales ALTER COLUMN payment_amount TYPE numeric(18,2) USING payment_amount::numeric(18,2);
CREATE UNIQUE INDEX IF NOT EXISTS godiyak_sales_event_idx
 ON mart.f_sales(date_id,source_uniq_id,status) WHERE source_uniq_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS mart.f_customer_retention (
 new_customers_count bigint NOT NULL,
 returning_customers_count bigint NOT NULL,
 refunded_customer_count bigint NOT NULL,
 period_name varchar(10) NOT NULL CHECK (period_name='weekly'),
 period_id integer NOT NULL CHECK (period_id BETWEEN 1 AND 53),
 item_id bigint NOT NULL,
 new_customers_revenue numeric(18,2) NOT NULL,
 returning_customers_revenue numeric(18,2) NOT NULL,
 customers_refunded bigint NOT NULL,
 week_start date NOT NULL,
 PRIMARY KEY(week_start,item_id)
);
-- Без week_start нельзя восстановить год недели; такую таблицу нужно мигрировать отдельно.
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='mart'
   AND table_name='f_customer_retention' AND column_name='week_start')
 THEN RAISE EXCEPTION 'Existing retention has no week_start; migrate it explicitly before this project'; END IF;
 IF EXISTS(SELECT 1 FROM staging.user_order_log WHERE status NOT IN ('shipped','refunded'))
 OR EXISTS(SELECT 1 FROM mart.f_sales WHERE status NOT IN ('shipped','refunded'))
 THEN RAISE EXCEPTION 'Unknown historical order status'; END IF;
END $$;
CREATE TABLE IF NOT EXISTS etl.report_state (
 pipeline_key text PRIMARY KEY, report_id text NOT NULL,
 initialized_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS etl.load_audit (
 run_id bigserial PRIMARY KEY, pipeline_key text NOT NULL, load_kind text NOT NULL,
 business_date date, source_id text NOT NULL, orders_count bigint NOT NULL,
 file_checksums jsonb NOT NULL, completed_at timestamptz NOT NULL DEFAULT now()
);
