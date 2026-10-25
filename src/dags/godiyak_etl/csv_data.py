"""Разбор исходных CSV без преобразования денежных сумм в float."""
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Tuple


class DataError(ValueError):
    pass


def timestamp(value):
    value = str(value).strip()
    try:
        result = datetime.strptime(value, '%Y%m%d') if len(value) == 8 and value.isdigit() else datetime.fromisoformat(value)
    except ValueError as exc:
        raise DataError('Invalid source timestamp') from exc
    if result.tzinfo is not None:
        raise DataError('Source timezone must be agreed explicitly; expected naive timestamps')
    return result


def integer(value):
    try:
        n = Decimal(str(value).strip())
        if not n.is_finite() or n != n.to_integral_value() or not 0 <= n < 2**63:
            raise DataError('Expected nonnegative int64')
        return int(n)
    except (InvalidOperation, ValueError) as exc:
        raise DataError('Expected nonnegative int64') from exc


def money(value):
    try:
        n = Decimal(str(value).strip())
        if not n.is_finite() or abs(n) >= Decimal('10000000000000000') or n != n.quantize(Decimal('0.01')):
            raise DataError('Expected finite NUMERIC(18,2) amount')
        return n.quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise DataError('Expected finite NUMERIC(18,2) amount') from exc


def records(payload, required):
    try:
        reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
        fields = reader.fieldnames
        if not fields or len(set(fields)) != len(fields) or not set(required) <= set(fields):
            raise DataError('CSV is missing required columns or has duplicate headers')
        result = []
        for row in reader:
            if None in row or any(row.get(k) is None or not str(row[k]).strip() for k in required):
                raise DataError('CSV row is incomplete')
            result.append(row)
        return result
    except (UnicodeError, csv.Error) as exc:
        raise DataError('Invalid UTF-8 CSV') from exc


@dataclass(frozen=True)
class Order:
    uniq_id: str
    date_time: datetime
    city_id: int
    city_name: str
    customer_id: int
    first_name: str
    last_name: str
    item_id: int
    item_name: str
    quantity: int
    payment_amount: Decimal
    status: str

    def values(self):
        return tuple(self.__dict__.values())


def orders(payload):
    required = ['uniq_id', 'date_time', 'city_id', 'customer_id', 'item_id', 'quantity', 'payment_amount']
    unique = {}
    for r in records(payload, required):
        status = (r.get('status') or 'shipped').strip().lower() or 'shipped'
        if status not in ('shipped', 'refunded'):
            raise DataError('Unknown order status')
        event_id = r['uniq_id'].strip()
        if len(event_id) > 200:
            raise DataError('uniq_id is too long')
        amount = money(r['payment_amount'])
        if status == 'shipped' and amount < 0:
            raise DataError('Negative shipped amount is outside source contract')
        item = Order(event_id, timestamp(r['date_time']), integer(r['city_id']), r.get('city_name') or '',
                     integer(r['customer_id']), r.get('first_name') or '', r.get('last_name') or '',
                     integer(r['item_id']), r.get('item_name') or '', integer(r['quantity']), abs(amount), status)
        key = (item.date_time.date(), event_id, status)
        if key in unique and unique[key] != item:
            raise DataError('Conflicting rows with the same date, uniq_id and status')
        unique[key] = item
    return tuple(unique.values())


def activity(payload):
    result = {}
    for r in records(payload, ['date_time', 'action_id', 'customer_id', 'quantity']):
        row = (r.get('uniq_id'), timestamp(r['date_time']), integer(r['action_id']), integer(r['customer_id']), integer(r['quantity']))
        key = (row[0], row[1].date()) if row[0] else row
        if key in result and result[key] != row:
            raise DataError('Conflicting activity rows')
        result[key] = row
    return tuple(result.values())


def research(payload):
    result = {}
    for r in records(payload, ['date_id', 'category_id', 'geo_id', 'sales_qty', 'sales_amt']):
        row = (timestamp(r['date_id']), integer(r['category_id']), integer(r['geo_id']), integer(r['sales_qty']), money(r['sales_amt']))
        key = row[:3]
        if key in result and result[key] != row:
            raise DataError('Conflicting customer research rows')
        result[key] = row
    return tuple(result.values())


def prices(payload):
    # В price_log.csv две колонки без заголовка: название и цена.
    try:
        rows = list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))
    except (UnicodeError, csv.Error) as exc:
        raise DataError('Invalid price CSV') from exc
    if not rows:
        raise DataError('Empty price response has no CSV structure')
    if rows[0] == ['item_name', 'price']:
        rows = rows[1:]
    result = {}
    for row in rows:
        if len(row) != 2 or not row[0].strip():
            raise DataError('Expected item name and price')
        name, amount = row[0].strip(), money(row[1])
        if amount < 0 or name in result and result[name] != amount:
            raise DataError('Invalid or conflicting product price')
        result[name] = amount
    return tuple(sorted(result.items()))


@dataclass(frozen=True)
class Bundle:
    orders: Tuple[Order, ...]
    activities: tuple = ()
    researches: tuple = ()
    prices: tuple = ()
    checksums: tuple = ()

    @classmethod
    def from_files(cls, files: Dict[str, bytes], increment=False):
        import hashlib
        suffix = '_inc' if increment else ''
        required = ['user_order_log' + suffix + '.csv', 'user_activity_log' + suffix + '.csv', 'customer_research' + suffix + '.csv']
        if not increment:
            required.append('price_log.csv')
        if not set(required) <= set(files):
            raise DataError('Incomplete report: not all required files were downloaded')
        return cls(orders(files[required[0]]), activity(files[required[1]]), research(files[required[2]]),
                   () if increment else prices(files['price_log.csv']),
                   tuple((name, hashlib.sha256(files[name]).hexdigest()) for name in sorted(required)))

    def validate_day(self, day):
        # Не заменяем день, если в файлах есть данные за другую дату.
        if any(x.date_time.date() != day for x in self.orders) or any(x[1].date() != day for x in self.activities) or any(x[0].date() != day for x in self.researches):
            raise DataError('Increment contains data outside the requested business date')
