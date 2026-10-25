"""Проверка импорта DAG и зависимостей задач без их запуска."""
import json,sys
sys.path.insert(0,'/work/dags')
import airflow
from airflow.models import DagBag
bag=DagBag(dag_folder='/work/dags',include_examples=False)
if bag.import_errors:
    print(json.dumps({'ok':False,'errors':bag.import_errors},ensure_ascii=False));sys.exit(1)
dag=bag.dags.get('godiyak_sales_retention')  # Берём разобранный DAG без обращения к базе Airflow.
assert dag is not None
assert set(dag.task_ids)=={'migrate_schema','prepare_report','load_increment'}
assert dag.get_task('load_increment').upstream_task_ids=={'prepare_report'}
assert dag.get_task('prepare_report').upstream_task_ids=={'migrate_schema'}
assert dag.max_active_runs==1 and not dag.catchup
print(json.dumps({'ok':True,'airflow':airflow.__version__,'dag_id':dag.dag_id,'tasks':dag.task_ids,'dependencies_verified':True,'network_used':False,'task_execution_performed':False},ensure_ascii=False))
