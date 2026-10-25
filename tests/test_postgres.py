import json,os,unittest
from dataclasses import replace
from datetime import date,timedelta
from decimal import Decimal
from godiyak_etl.api import Client,IncrementUnavailable
from godiyak_etl.csv_data import Bundle,DataError
from godiyak_etl.pipeline import ensure_report,load_increment
from godiyak_etl.store import Store
from helpers import FIX,bundle,files


@unittest.skipUnless(os.environ.get('ETL_TEST_DSN'),'Integration tests require an isolated ETL_TEST_DSN')
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        cls.connect=staticmethod(lambda:psycopg2.connect(os.environ['ETL_TEST_DSN']))
        with cls.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT current_database()');name=cur.fetchone()[0]
                if not name.startswith('godiyak_etl_test'):
                    raise RuntimeError('Refusing destructive test setup outside godiyak_etl_test* database')
    def sql(self,sql,args=None):
        with self.connect() as c:
            with c.cursor() as cur:
                cur.execute(sql,args)
                if cur.description:return cur.fetchall()
    def setUp(self):
        self.sql('DROP SCHEMA IF EXISTS mart CASCADE;DROP SCHEMA IF EXISTS staging CASCADE;DROP SCHEMA IF EXISTS etl CASCADE')
        self.store=Store(self.connect);self.store.migrate()
    def load(self,ev):
        for ds in sorted({e['date_time'][:10] for e in ev}):self.store.publish_day(date.fromisoformat(ds),'I',bundle([e for e in ev if e['date_time'].startswith(ds)]))
    def facts(self):return self.sql('SELECT c.date_actual,item_id,customer_id,quantity,payment_amount,status,source_uniq_id FROM mart.f_sales f JOIN mart.d_calendar c USING(date_id) ORDER BY 1,2,3,7')
    def retention(self):return self.sql('SELECT period_id,item_id,new_customers_count,returning_customers_count,refunded_customer_count,new_customers_revenue,returning_customers_revenue,customers_refunded,week_start FROM mart.f_customer_retention ORDER BY week_start,item_id')
    def test_full_control_set_and_all_retention_fields(self):
        self.load(FIX['input_events']);f=self.facts();self.assertEqual(len(f),11);self.assertEqual(sum(x[4] for x in f),Decimal('1350.00'))
        actual=[list(x[:8]) for x in self.retention()]
        expected=[[x['period_id'],x['item_id'],x['new_customers_count'],x['returning_customers_count'],x['refunded_customer_count'],Decimal(x['new_customers_revenue']),Decimal(x['returning_customers_revenue']),x['customers_refunded']]for x in FIX['expected_retention_by_revenue_policy']['gross_shipped']]
        self.assertEqual(actual,expected);self.assertFalse(any(self.store.checks(date(2026,4,12)).values()))
    def test_micro_cases_refund_events_not_units_and_decimals(self):
        for case in FIX['micro_cases']:
            with self.subTest(case=case['id']):
                self.setUp();self.load(case['events']);e=case['expected'];f=self.facts();r=self.retention()[0]
                self.assertEqual((len(f),sum(x[4]for x in f)),(e['sales_rows'],Decimal(e['total_revenue'])))
                self.assertEqual(list(r[2:8]),[e['new_customers_count'],e['returning_customers_count'],e['refunded_customer_count'],Decimal(e['new_customers_revenue']['gross_shipped']),Decimal(e['returning_customers_revenue']['gross_shipped']),e['customers_refunded']])
    def test_old_csv_in_real_database(self):
        ev=FIX['micro_cases'][1]['events'][:1];self.store.publish_day(date(2026,4,6),'old',bundle(ev,old=True));self.assertEqual(self.facts()[0][5],'shipped')
    def test_csv_replay_unchanged(self):
        self.load(FIX['input_events']);before=(self.facts(),self.retention());self.load(FIX['input_events']);self.assertEqual(before,(self.facts(),self.retention()))
    def test_all_three_sunday_corrections(self):
        for c in FIX['corrected_sunday_scenarios']:
            with self.subTest(c=c['id']):
                self.setUp();self.load(FIX['input_events']);self.store.publish_day(date(2026,4,12),'fixed',bundle(c['new_events']));f=self.facts()
                self.assertEqual((len(f),sum(x[4]for x in f)),(c['expected_sales_rows'],Decimal(c['expected_total_revenue'])))
                r=[r for r in self.retention() if r[0]==15 and r[1]==20]
                if c['id']=='add_order':self.assertEqual(list(r[0][2:8]),[0,1,0,Decimal(0),Decimal(120),0])
                elif c['id']=='change_amount':self.assertEqual(r[0][5],Decimal(80))
                else:self.assertEqual(r,[])
    def test_sql_component_replay_unchanged(self):
        from godiyak_etl.store import SQL_DIR
        self.load(FIX['input_events']);before=(self.facts(),self.retention())
        days=sorted({date.fromisoformat(e['date_time'][:10])for e in FIX['input_events']});args={'days':days,'weeks':sorted({d-timedelta(days=d.weekday())for d in days})}
        with self.store.transaction() as cur:
            for name in ['003_sales.sql','004_retention.sql']:cur.execute((SQL_DIR/name).read_text(),args)
        self.assertEqual(before,(self.facts(),self.retention()))
    def test_equal_amount_and_timestamp_distinct_ids_survive(self):
        ev=[dict(e,date_time='2026-04-07T10:00:00',payment_amount='200.00')for e in FIX['micro_cases'][1]['events'][1:]];self.load(ev)
        self.assertEqual(len(self.facts()),2);self.assertEqual(self.retention()[0][6],Decimal(400))
    def test_same_week_number_different_years_do_not_collide(self):
        ev=[dict(FIX['input_events'][0],event_key='y1',date_time='2025-01-01T10:00:00'),dict(FIX['input_events'][0],event_key='y2',date_time='2026-01-01T10:00:00')];self.load(ev)
        self.assertEqual([x[0]for x in self.retention()],[1,1]);self.assertNotEqual(self.retention()[0][8],self.retention()[1][8])
    def test_iso_week_spans_calendar_year(self):
        ev=[dict(FIX['input_events'][0],event_key='ny1',date_time='2025-12-31T10:00:00'),dict(FIX['input_events'][0],event_key='ny2',date_time='2026-01-01T10:00:00')];self.load(ev)
        self.assertEqual(len(self.retention()),1);self.assertEqual(self.retention()[0][3],1)
    def test_failure_after_deletes_rolls_back_entire_day(self):
        self.load(FIX['input_events']);before=(self.facts(),self.retention())
        self.sql("CREATE FUNCTION mart.reject_test_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected fault'; END $$;CREATE TRIGGER reject_test_update BEFORE INSERT ON mart.f_customer_retention FOR EACH ROW EXECUTE FUNCTION mart.reject_test_update();")
        with self.assertRaises(Exception):self.store.publish_day(date(2026,4,12),'bad',bundle(FIX['corrected_sunday_scenarios'][1]['new_events']))
        self.assertEqual(before,(self.facts(),self.retention()));self.assertEqual(self.sql("SELECT payment_amount FROM staging.user_order_log WHERE uniq_id='d1'")[0][0],Decimal(50))
    def test_missing_increment_leaves_existing_day(self):
        self.load(FIX['input_events']);before=(self.facts(),self.retention());client=Client('godiyak_yaroslav','1','test-only',transport=lambda *a:b'{"status":"NOT FOUND"}')
        with self.assertRaises(IncrementUnavailable):load_increment(client,self.store,'R',date(2026,4,12))
        self.assertEqual(before,(self.facts(),self.retention()))
    def test_legacy_fact_migration_keeps_history_and_is_repeatable(self):
        self.sql('DROP SCHEMA mart CASCADE;DROP SCHEMA staging CASCADE;DROP SCHEMA etl CASCADE;CREATE SCHEMA mart;CREATE TABLE mart.f_sales(id bigserial PRIMARY KEY,date_id int,item_id int,customer_id int,city_id int,quantity int,payment_amount numeric(14,2));INSERT INTO mart.f_sales(date_id,item_id,customer_id,city_id,quantity,payment_amount) VALUES(20260401,10,1,1,1,12.34)')
        self.store.migrate();self.store.migrate();self.assertEqual(self.sql('SELECT quantity,payment_amount,status FROM mart.f_sales'),[(1,Decimal('12.34'),'shipped')])
    def test_api_to_postgres_bootstrap_and_increment(self):
        before=[FIX['input_events'][0]];after=[e for e in FIX['input_events'] if e['date_time'].startswith('2026-04-07')];calls=[]
        def transport(method,url,headers):
            calls.append(url)
            if url.endswith('/generate_report'):return b'{"task_id":"T"}'
            if '/get_report?' in url:return b'{"status":"SUCCESS","data":{"report_id":"R"}}'
            if '/get_increment?' in url:return b'{"status":"SUCCESS","data":{"increment_id":"I"}}'
            name=url.rsplit('/',1)[1];return (files(after,True) if '_inc.csv'in name else files(before))[name]
        client=Client('godiyak_yaroslav','1','test-only',transport=transport)
        report=ensure_report(client,self.store);self.assertEqual(report,'R');ensure_report(client,self.store);self.assertEqual(sum('/generate_report'in u for u in calls),1)
        load_increment(client,self.store,report,date(2026,4,7));load_increment(client,self.store,report,date(2026,4,7));self.assertEqual(len(self.facts()),3)
        self.assertEqual(self.sql('SELECT count(*) FROM staging.price_log')[0][0],1)
    def install_actual_course_schema(self):
        from pathlib import Path
        self.sql('DROP SCHEMA mart CASCADE;DROP SCHEMA staging CASCADE;DROP SCHEMA etl CASCADE')
        self.sql((Path(__file__).parent/'fixtures/course_baseline.sql').read_text())
        self.store.migrate()
    def test_actual_course_schema_end_to_end(self):
        self.install_actual_course_schema();self.load(FIX['input_events'])
        self.assertEqual(len(self.facts()),11);self.assertEqual(sum(x[4]for x in self.facts()),Decimal('1350.00'));self.assertEqual(len(self.retention()),4)
        self.store.migrate();self.load(FIX['input_events']);self.assertEqual(len(self.facts()),11)
    def test_actual_course_uuid_pk_migrates_for_separate_refund(self):
        self.install_actual_course_schema()
        ev=FIX['micro_cases'][0]['events'];ev=[ev[0],dict(ev[1],event_key=ev[0]['event_key'])];self.load(ev)
        self.assertEqual(len(self.facts()),2);self.assertEqual(sum(x[4]for x in self.facts()),Decimal(0))
        self.load(ev);self.assertEqual(len(self.facts()),2)
    def test_auxiliary_increment_also_replaced(self):
        day=date(2026,4,6);from datetime import datetime
        b=replace(bundle(FIX['input_events'][:1]),activities=(('u',datetime(2026,4,6,10),1,1,1),),researches=((datetime(2026,4,6),10,1,1,Decimal('100.00')),))
        self.store.publish_day(day,'I',b);self.store.publish_day(day,'I',b)
        self.assertEqual(self.sql('SELECT count(*) FROM staging.user_activity_log')[0][0],1);self.assertEqual(self.sql('SELECT count(*) FROM staging.customer_research')[0][0],1)


if __name__=='__main__':unittest.main()
