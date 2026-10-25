"""Атомарная публикация дня: staging -> dimensions -> sales -> retention -> audit."""
import json
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from .csv_data import DataError

SQL_DIR = Path(__file__).resolve().parent / 'sql'
LOCK_KEY = 782650026


class Store:
    def __init__(self, connect, pipeline_key='godiyak_sales'):
        self.connect, self.pipeline_key = connect, pipeline_key

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT pg_advisory_xact_lock(%s)', (LOCK_KEY,))
                    yield cur
        finally:
            conn.close()

    def migrate(self):
        with self.transaction() as cur:
            cur.execute((SQL_DIR / '001_schema.sql').read_text())

    def report_id(self):
        with self.transaction() as cur:
            return self._state(cur)

    def _state(self, cur):
        cur.execute('SELECT report_id FROM etl.report_state WHERE pipeline_key=%s', (self.pipeline_key,))
        row = cur.fetchone()
        return row[0] if row else None

    def initialize(self, report_id, bundle):
        if not bundle.orders:
            raise DataError('Initial snapshot contains no orders; refusing to initialize')
        # Пока API готовил отчёт, другой запуск мог уже загрузить начальные данные.
        with self.transaction() as cur:
            existing = self._state(cur)
            if existing:
                return existing
            self._publish(cur, bundle, None, report_id)
            cur.execute('INSERT INTO etl.report_state(pipeline_key,report_id) VALUES(%s,%s)', (self.pipeline_key, report_id))
            return report_id

    def publish_day(self, day, source_id, bundle):
        bundle.validate_day(day)  # Проверяем весь CSV до DELETE.
        with self.transaction() as cur:
            self._publish(cur, bundle, day, source_id)

    @staticmethod
    def _replace(cur, table, date_column, fields, rows, dates):
        if dates:
            cur.execute('DELETE FROM ' + table + ' WHERE ' + date_column + '::date=ANY(%s::date[])', (sorted(dates),))
        if rows:
            from psycopg2.extras import execute_values
            execute_values(cur, 'INSERT INTO ' + table + '(' + ','.join(fields) + ') VALUES %s', rows, page_size=1000)

    def _publish(self, cur, bundle, day, source_id):
        days = {day} if day else {x.date_time.date() for x in bundle.orders}
        self._replace(cur, 'staging.user_order_log', 'date_time',
                      ('uniq_id','date_time','city_id','city_name','customer_id','first_name','last_name','item_id','item_name','quantity','payment_amount','status'),
                      [x.values() for x in bundle.orders], days)
        self._replace(cur, 'staging.user_activity_log', 'date_time',
                      ('uniq_id','date_time','action_id','customer_id','quantity'), bundle.activities,
                      {day} if day else {x[1].date() for x in bundle.activities})
        self._replace(cur, 'staging.customer_research', 'date_id',
                      ('date_id','category_id','geo_id','sales_qty','sales_amt'), bundle.researches,
                      {day} if day else {x[0].date() for x in bundle.researches})
        if day is None:
            cur.execute('DELETE FROM staging.price_log')
            if bundle.prices:
                from psycopg2.extras import execute_values
                execute_values(cur, 'INSERT INTO staging.price_log(item_name,price) VALUES %s', bundle.prices, page_size=1000)
        args = {'days': sorted(days), 'weeks': sorted({d - timedelta(days=d.weekday()) for d in days})}
        for name in ['002_dimensions.sql', '003_sales.sql', '004_retention.sql']:
            cur.execute((SQL_DIR / name).read_text(), args)
        cur.execute('''SELECT count(*),coalesce(sum(payment_amount),0)
          FROM mart.f_sales f JOIN mart.d_calendar c USING(date_id)
          WHERE c.date_actual=ANY(%s::date[])''', (sorted(days),))
        count, revenue = cur.fetchone()
        expected = sum((-x.payment_amount if x.status == 'refunded' else x.payment_amount for x in bundle.orders), 0)
        if count != len(bundle.orders) or revenue != expected:
            raise DataError('Published sales failed row-count or revenue reconciliation; transaction rolled back')
        cur.execute('''INSERT INTO etl.load_audit(pipeline_key,load_kind,business_date,source_id,orders_count,file_checksums)
          VALUES(%s,%s,%s,%s,%s,%s::jsonb)''',
                    (self.pipeline_key, 'increment' if day else 'snapshot', day, source_id, len(bundle.orders), json.dumps(dict(bundle.checksums))))

    def checks(self, day):
        with self.transaction() as cur:
            cur.execute('''SELECT count(*) FROM (
              SELECT date_id,source_uniq_id,status FROM mart.f_sales
              WHERE source_uniq_id IS NOT NULL GROUP BY date_id,source_uniq_id,status HAVING count(*)>1
            ) q''')
            duplicates = cur.fetchone()[0]
            cur.execute('''SELECT count(*) FROM mart.f_sales WHERE status NOT IN ('shipped','refunded')
              OR (status='refunded' AND (payment_amount>0 OR quantity>0))''')
            bad_signs = cur.fetchone()[0]
            cur.execute('''SELECT count(*) FROM mart.f_customer_retention
              WHERE period_name<>'weekly' OR period_id<>extract(week FROM week_start)
              OR customers_refunded<refunded_customer_count
              OR new_customers_count<0 OR returning_customers_count<0 OR customers_refunded<0''')
            bad_retention = cur.fetchone()[0]
            cur.execute('''SELECT count(*) FROM (SELECT week_start,item_id FROM mart.f_customer_retention
              GROUP BY week_start,item_id HAVING count(*)>1)q''')
            retention_duplicates = cur.fetchone()[0]
            result = dict(sales_duplicate_keys=duplicates, bad_refund_signs=bad_signs,
                          bad_retention=bad_retention, retention_duplicate_keys=retention_duplicates)
            if any(result.values()):
                raise DataError('Warehouse quality checks failed: ' + json.dumps(result))
            return result
