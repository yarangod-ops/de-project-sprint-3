#!/usr/bin/env python3
"""CLI: те же API/SQL и атомарная публикация, что в DAG."""
import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'dags'))
from godiyak_etl.api import Client
from godiyak_etl.pipeline import ensure_report, load_increment
from godiyak_etl.store import Store


def main():
    import psycopg2
    parser = argparse.ArgumentParser(description='ETL — Годияк Ярослав, М25-555')
    parser.add_argument('--date', type=date.fromisoformat, help='Дата инкремента YYYY-MM-DD')
    parser.add_argument('--bootstrap-only', action='store_true', help='Первичная загрузка без запроса инкремента')
    args = parser.parse_args()
    if not args.bootstrap_only and args.date is None:
        parser.error('Specify --date or --bootstrap-only')
    # PG* читает libpq: пароль не передаётся аргументом командной строки и не печатается.
    client = Client(os.environ.get('ETL_NICKNAME','godiyak_yaroslav'), os.environ.get('ETL_COHORT',''),
                    os.environ.get('ETL_API_KEY',''), base_url=os.environ.get('ETL_API_URL','https://d5dg1j9kt695d30blp03.apigw.yandexcloud.net'))
    store = Store(lambda: psycopg2.connect(''), 'godiyak_sales_' + client.cohort + '_' + client.nickname)
    store.migrate()
    report_id = ensure_report(client, store)
    result = {'report_id':report_id,'bootstrap':'ready'}
    if args.date:
        result.update(load_increment(client, store, report_id, args.date))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
