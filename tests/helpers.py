import csv,io,json
from pathlib import Path
from godiyak_etl.csv_data import Bundle,orders
FIX=json.loads((Path(__file__).parent/'fixtures/control_cases.json').read_text())


def csv_bytes(events,old=False):
    fields=['id','uniq_id','date_time','city_id','city_name','customer_id','first_name','last_name','item_id','item_name','quantity','payment_amount']+([] if old else ['status'])
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for n,e in enumerate(events,1):
        row=dict(id=n,uniq_id=e['event_key'],date_time=e['date_time'],city_id=1,city_name='city',customer_id=ord(e['customer_id'])-64,first_name='first',last_name='last',item_id=e['item_id'],item_name='item'+str(e['item_id']),quantity=e['quantity'],payment_amount=e['payment_amount'])
        if not old:row['status']=e.get('status','shipped')
        writer.writerow(row)
    return stream.getvalue().encode()


def bundle(events,old=False):
    return Bundle(orders(csv_bytes(events,old)))


def files(events,increment=False,old=False):
    suffix='_inc' if increment else ''
    data={'user_order_log'+suffix+'.csv':csv_bytes(events,old),
          'user_activity_log'+suffix+'.csv':b'uniq_id,date_time,action_id,customer_id,quantity\n',
          'customer_research'+suffix+'.csv':b'date_id,category_id,geo_id,sales_qty,sales_amt\n'}
    if not increment:data['price_log.csv']=b'item_name,price\nMilk,100.00\n'
    return data
