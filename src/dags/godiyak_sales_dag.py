"""Загрузка продаж и недельной витрины клиентов."""
from datetime import date, datetime, timedelta

from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

from godiyak_etl.api import Client
from godiyak_etl.pipeline import ensure_report, load_increment
from godiyak_etl.store import Store


def services():
    # Connections/Variables читаются только во время задачи, не при парсинге DAG.
    api = BaseHook.get_connection('godiyak_practicum_api')
    nickname = Variable.get('godiyak_nickname', default_var='godiyak_yaroslav')
    cohort = Variable.get('godiyak_cohort', default_var='')
    client = Client(nickname, cohort, api.password, base_url=api.host or 'https://d5dg1j9kt695d30blp03.apigw.yandexcloud.net')
    store = Store(lambda: PostgresHook(postgres_conn_id='godiyak_postgres').get_conn(),
                  pipeline_key='godiyak_sales_' + str(cohort) + '_' + nickname)
    return client, store


def migrate_schema():
    Store(lambda: PostgresHook(postgres_conn_id='godiyak_postgres').get_conn()).migrate()


def prepare_report():
    client, store = services()
    return ensure_report(client, store)


def process_day(ti, ds, dag_run=None, **kwargs):
    conf = dag_run.conf if dag_run and dag_run.conf else {}
    business_date = date.fromisoformat(conf.get('business_date') or ds)
    client, store = services()
    return load_increment(client, store, ti.xcom_pull(task_ids='prepare_report'), business_date)


with DAG(
    dag_id='godiyak_sales_retention',
    description='М25-555: продажи, возвраты и недельная возвращаемость клиентов',
    default_args={'owner':'godiyak_yaroslav','retries':2,'retry_delay':timedelta(minutes=2),
                  'execution_timeout':timedelta(minutes=15)},
    start_date=datetime(2020,1,1),
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    tags=['МИФИ','М25-555','ETL','Годияк'],
) as dag:
    migration = PythonOperator(task_id='migrate_schema', python_callable=migrate_schema)
    report = PythonOperator(task_id='prepare_report', python_callable=prepare_report)
    increment = PythonOperator(task_id='load_increment', python_callable=process_day)
    migration >> report >> increment
