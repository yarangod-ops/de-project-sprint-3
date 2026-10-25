"""Оркестрация без зависимости от Airflow: тот же код используется CLI и тестами."""
from .csv_data import Bundle


def ensure_report(client, store):
    existing = store.report_id()
    if existing:
        return existing
    data = client.wait_report(client.create_report())
    bundle = Bundle.from_files(client.download_files(data))
    return store.initialize(data['report_id'], bundle)


def load_increment(client, store, report_id, day):
    data = client.get_increment(report_id, day)
    bundle = Bundle.from_files(client.download_files(data, increment=True), increment=True)
    store.publish_day(day, data['increment_id'], bundle)
    return {'business_date': day.isoformat(), 'orders': len(bundle.orders), 'quality': store.checks(day)}
