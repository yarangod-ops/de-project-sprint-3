"""Три метода учебного API и скачивание файлов без передачи API-ключа в S3."""
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    pass


class IncrementUnavailable(ApiError):
    """API не вернул инкремент; прежние данные должны сохраниться."""


class Client:
    REPORT_FILES = ('customer_research.csv', 'user_order_log.csv', 'user_activity_log.csv', 'price_log.csv')
    INCREMENT_FILES = ('customer_research_inc.csv', 'user_order_log_inc.csv', 'user_activity_log_inc.csv')

    def __init__(self, nickname, cohort, api_key,
                 base_url='https://d5dg1j9kt695d30blp03.apigw.yandexcloud.net',
                 transport=None, sleep=time.sleep, poll_attempts=75):
        if not nickname or not re.fullmatch(r'[A-Za-z0-9_-]+', nickname):
            raise ValueError('Set an alphanumeric ETL_NICKNAME')
        if not cohort or not re.fullmatch(r'[0-9]+', str(cohort)):
            raise ValueError('Set ETL_COHORT to your API cohort number; this is not the university group')
        if not api_key:
            raise ValueError('Set the API key in the Airflow Connection password or local environment')
        if urlsplit(base_url).scheme != 'https':
            raise ValueError('API endpoint must use HTTPS')
        self.base_url = base_url.rstrip('/')
        self.nickname, self.cohort = nickname, str(cohort)
        self.headers = {'X-Nickname': nickname, 'X-Cohort': self.cohort, 'X-Project': 'True', 'X-API-KEY': api_key}
        self.transport, self.sleep = transport or self._http, sleep
        self.poll_attempts = poll_attempts

    @staticmethod
    def _http(method, url, headers):
        request = Request(url, headers=headers, data=b'' if method == 'POST' else None, method=method)
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    payload = response.read(50 * 1024 * 1024 + 1)
                    if len(payload) > 50 * 1024 * 1024:
                        raise ApiError('Response exceeds 50 MiB')
                    return payload
            except HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise ApiError('HTTP request failed with status ' + str(exc.code)) from None
                if attempt == 2:
                    raise ApiError('HTTP service unavailable after retries') from None
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise ApiError('Network unavailable after retries') from None
            time.sleep(2**attempt)
        raise ApiError('HTTP request failed')

    def _json(self, method, endpoint, params=None):
        url = self.base_url + endpoint + ('?' + urlencode(params) if params else '')
        try:
            result = json.loads(self.transport(method, url, self.headers))
        except (ValueError, UnicodeError):
            raise ApiError('API did not return valid JSON') from None
        if not isinstance(result, dict):
            raise ApiError('API JSON must be an object')
        return result

    @staticmethod
    def _identifier(data, key):
        value = data.get(key)
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_=-]+', value):
            raise ApiError('Missing or invalid API identifier: ' + key)
        return value

    def create_report(self):
        return self._identifier(self._json('POST', '/generate_report'), 'task_id')

    def wait_report(self, task_id):
        for attempt in range(self.poll_attempts):
            result = self._json('GET', '/get_report', {'task_id': task_id})
            if result.get('status') == 'SUCCESS':
                data = result.get('data')
                if not isinstance(data, dict):
                    raise ApiError('get_report has no data object')
                self._identifier(data, 'report_id')
                return data
            if result.get('status') != 'RUNNING':
                raise ApiError('Report generation failed or returned an unknown status')
            if attempt < self.poll_attempts - 1:
                self.sleep(2)
        raise ApiError('Report generation timed out')

    def get_increment(self, report_id, day):
        result = self._json('GET', '/get_increment', {'report_id': report_id, 'date': day.isoformat() + 'T00:00:00'})
        if result.get('status') != 'SUCCESS':
            raise IncrementUnavailable('Increment is not available; existing warehouse data was not deleted')
        data = result.get('data')
        if not isinstance(data, dict):
            raise ApiError('get_increment has no data object')
        self._identifier(data, 'increment_id')
        return data

    def file_url(self, data, filename, increment=False):
        allowed = self.INCREMENT_FILES if increment else self.REPORT_FILES
        if filename not in allowed:
            raise ValueError('Unexpected report filename')
        object_id = self._identifier(data, 'increment_id' if increment else 'report_id')
        supplied = data.get('s3_path')
        if isinstance(supplied, dict):
            supplied = supplied.get(filename)
        if supplied:
            if not isinstance(supplied, str):
                raise ApiError('Unsupported s3_path format')
            parsed = urlsplit(supplied)
            if parsed.scheme != 'https' or parsed.hostname != 'storage.yandexcloud.net' or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ApiError('Untrusted or unsupported S3 URL')
            if parsed.path.endswith('.csv'):
                if not parsed.path.endswith('/' + filename):
                    raise ApiError('s3_path refers to a different CSV')
                return supplied
            return supplied.rstrip('/') + '/' + filename
        return 'https://storage.yandexcloud.net/s3-sprint3/cohort_{}/{}/project/{}/{}'.format(
            quote(self.cohort, safe=''), quote(self.nickname, safe=''), quote(object_id, safe=''), filename)

    def download_files(self, data, increment=False):
        names = self.INCREMENT_FILES if increment else self.REPORT_FILES
        return {name: self.transport('GET', self.file_url(data, name, increment), {}) for name in names}
