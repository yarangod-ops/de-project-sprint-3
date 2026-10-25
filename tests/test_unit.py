import json,unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs,urlsplit
from godiyak_etl.api import ApiError,Client,IncrementUnavailable
from godiyak_etl.csv_data import Bundle,DataError,money,orders,prices
from helpers import FIX,bundle,csv_bytes,files


class CsvTests(unittest.TestCase):
    def test_old_format_defaults_to_shipped(self):
        self.assertEqual(bundle(FIX['micro_cases'][1]['events'],old=True).orders[0].status,'shipped')
    def test_decimal_is_exact(self):
        self.assertEqual(sum(x.payment_amount for x in bundle(FIX['micro_cases'][1]['events']).orders),Decimal('600.55'))
    def test_identical_duplicates_are_removed(self):
        ev=FIX['input_events'][0];self.assertEqual(len(bundle([ev,ev]).orders),1)
    def test_distinct_ids_with_same_values_survive(self):
        ev=FIX['input_events'][0];self.assertEqual(len(bundle([ev,dict(ev,event_key='another')]).orders),2)
    def test_conflicting_duplicate_is_rejected(self):
        ev=FIX['input_events'][0]
        with self.assertRaises(DataError):bundle([ev,dict(ev,payment_amount='80.00')])
    def test_invalid_money_rejected(self):
        for value in ['NaN','Infinity','0.001','10000000000000000']:
            with self.subTest(value=value),self.assertRaises(DataError):money(value)
    def test_unknown_status_rejected(self):
        with self.assertRaises(DataError):bundle([dict(FIX['input_events'][0],status='cancelled')])
    def test_bad_csv_does_not_become_empty_day(self):
        for value in [b'',b'error\nserver unavailable',b'uniq_id,uniq_id\n1,2']:
            with self.subTest(value=value),self.assertRaises(DataError):orders(value)
    def test_empty_csv_with_correct_headers_is_confirmed_empty(self):
        self.assertEqual(bundle([]).orders,())
    def test_foreign_date_rejected(self):
        with self.assertRaises(DataError):bundle(FIX['input_events']).validate_day(date(2026,4,6))
    def test_all_report_files_required(self):
        f=files(FIX['input_events']);del f['price_log.csv']
        with self.assertRaises(DataError):Bundle.from_files(f)
    def test_headerless_price_keeps_first_item(self):
        self.assertEqual(prices('Молоко,100\nХлеб,30.25\n'.encode()),(('Молоко',Decimal('100.00')),('Хлеб',Decimal('30.25'))))
    def test_price_with_header_also_supported(self):
        self.assertEqual(prices(b'item_name,price\nMilk,100\n'),(('Milk',Decimal('100.00')),))
    def test_negative_refund_amount_normalized_once(self):
        self.assertEqual(bundle([dict(FIX['micro_cases'][0]['events'][1],payment_amount='-100.00')]).orders[0].payment_amount,Decimal('100.00'))


class ApiTests(unittest.TestCase):
    def make(self,transport):return Client('godiyak_yaroslav','1','test-only',transport=transport,sleep=lambda _:None,poll_attempts=3)
    def test_three_methods_headers_dates_and_all_seven_urls(self):
        calls=[];poll=[0]
        def fake(method,url,headers):
            calls.append((method,url,dict(headers)));u=urlsplit(url)
            if u.path=='/generate_report':return b'{"task_id":"TASK"}'
            if u.path=='/get_report':
                poll[0]+=1
                return json.dumps({'status':'RUNNING'} if poll[0]==1 else {'status':'SUCCESS','data':{'report_id':'REPORT'}}).encode()
            if u.path=='/get_increment':
                self.assertEqual(parse_qs(u.query),{'report_id':['REPORT'],'date':['2026-04-12T00:00:00']})
                return b'{"status":"SUCCESS","data":{"increment_id":"INC"}}'
            self.assertEqual(headers,{})
            self.assertEqual(u.hostname,'storage.yandexcloud.net')
            self.assertIn('/cohort_1/godiyak_yaroslav/project/',u.path)
            return b'CSV'
        c=self.make(fake);data=c.wait_report(c.create_report());self.assertEqual(len(c.download_files(data)),4)
        inc=c.get_increment('REPORT',date(2026,4,12));self.assertEqual(len(c.download_files(inc,True)),3)
        for method,url,headers in calls:
            if urlsplit(url).hostname!='storage.yandexcloud.net':self.assertEqual(headers,{'X-Nickname':'godiyak_yaroslav','X-Cohort':'1','X-Project':'True','X-API-KEY':'test-only'})
    def test_poll_timeout_is_error(self):
        with self.assertRaises(ApiError):self.make(lambda *a:b'{"status":"RUNNING"}').wait_report('T')
    def test_missing_increment_is_not_empty_csv(self):
        with self.assertRaises(IncrementUnavailable):self.make(lambda *a:b'{"status":"NOT FOUND"}').get_increment('R',date(2026,4,12))
    def test_s3_path_supplied_by_api(self):
        c=self.make(None);self.assertEqual(c.file_url({'report_id':'R','s3_path':'https://storage.yandexcloud.net/s3-sprint3/folder'},'price_log.csv'),'https://storage.yandexcloud.net/s3-sprint3/folder/price_log.csv')
    def test_s3_path_cannot_exfiltrate_key(self):
        with self.assertRaises(ApiError):self.make(None).file_url({'report_id':'R','s3_path':'https://example.com/file'},'price_log.csv')
    def test_bad_json_and_failed_report(self):
        for response in [b'<html>bad</html>',b'[]',b'{"status":"FAILED"}']:
            with self.subTest(response=response),self.assertRaises(ApiError):self.make(lambda *a:response).wait_report('T')


if __name__=='__main__':unittest.main()
