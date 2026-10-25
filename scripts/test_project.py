#!/usr/bin/env python3
"""Запуск unit+PostgreSQL тестов в отдельном временном контейнере, без общих баз."""
import argparse,json,os,subprocess,sys,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'/'dags'),str(ROOT/'tests')]


def docker(*args,check=True):
    return subprocess.run(['docker',*args],capture_output=True,text=True,check=check)


def main():
    p=argparse.ArgumentParser();p.add_argument('--unit-only',action='store_true');args=p.parse_args()
    name='godiyak-etl-test-'+str(os.getpid());created=False;report={}
    if not args.unit_only:
        import psycopg2  # Сначала проверяем зависимость, затем создаём контейнер.
    try:
        if not args.unit_only:
            docker('run','--detach','--rm','--name',name,'--read-only',
                   '--tmpfs','/var/lib/postgresql/data:rw,size=256m','--tmpfs','/var/run/postgresql:rw,size=8m',
                   '--tmpfs','/tmp:rw,size=16m','--publish','127.0.0.1::5432',
                   '--env','POSTGRES_HOST_AUTH_METHOD=trust','postgres:17-alpine');created=True
            # Временный сервер инициализации доступен через сокет; ждём основной сервер по TCP.
            for _ in range(60):
                if docker('exec',name,'pg_isready','-h','127.0.0.1','-U','postgres',check=False).returncode==0:break
                time.sleep(0.5)
            else:raise RuntimeError('Temporary PostgreSQL did not become ready')
            docker('exec',name,'psql','-U','postgres','-c','CREATE DATABASE godiyak_etl_test')
            port=docker('port',name,'5432').stdout.strip().rsplit(':',1)[1]
            os.environ['ETL_TEST_DSN']='host=127.0.0.1 port='+port+' dbname=godiyak_etl_test user=postgres connect_timeout=10'
            report['postgres_image_id']=json.loads(docker('inspect',name).stdout)[0]['Image']
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        report.update(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),ok=result.wasSuccessful(),live_api_checked=False,full_airflow_checked=False)
        return_code=0 if result.wasSuccessful() else 1
    finally:
        if created:docker('rm','-f',name,check=False)
        report['temporary_container_removed']=not created or not docker('ps','-a','--filter','name='+name,'--format','{{.Names}}').stdout.strip()
        report['shared_databases_used']=False
        (ROOT/'reports').mkdir(exist_ok=True)
        (ROOT/'reports/test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return return_code


if __name__=='__main__':sys.exit(main())
