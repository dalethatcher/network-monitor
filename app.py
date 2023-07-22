import logging
import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests
import schedule

ROOT = Path(__file__).parent
SQLITE_FILE = ROOT / 'monitor-db.sqlite'


class CheckResult:
    def __init__(self, check_type: str, result: str):
        self.at = datetime.now(timezone.utc)
        self.check_type = check_type
        self.result = result

    def __repr__(self):
        return str(self.__dict__)


class Database:
    def __init__(self):
        if not SQLITE_FILE.exists():
            self.__execute('''CREATE TABLE CHECK_LOG(
                EVENT_ID INTEGER PRIMARY KEY, AT TEXT, CHECK_TYPE TEXT, RESULT TEXT)''')

        self.entries = queue.Queue()
        entry_writer = threading.Thread(target=self.__insert_entries, daemon=True)
        entry_writer.start()

    @staticmethod
    def __on_cursor(f: Callable[[sqlite3.Cursor], None]):
        connection = sqlite3.connect(SQLITE_FILE)
        cursor = connection.cursor()
        f(cursor)
        cursor.close()
        connection.commit()
        connection.close()

    def __execute(self, sql: str):
        self.__on_cursor(lambda c: c.execute(sql))

    def __insert_entries(self):
        while True:
            entry: CheckResult = self.entries.get()

            logging.info(f"Writing check result to database: {entry}")
            self.__on_cursor(lambda c: c.execute('INSERT INTO CHECK_LOG (AT, CHECK_TYPE, RESULT) VALUES (?, ?, ?)', [
                entry.at.isoformat().replace('+00:00', 'Z'),
                entry.check_type,
                entry.result
            ]))

    def insert_check_result(self, entry: CheckResult):
        self.entries.put(entry)


def external_ip_check() -> CheckResult:
    try:
        response = requests.get('https://api.ipify.org', timeout=5)

        if response.status_code == 200:
            return CheckResult('EXTERNAL_IP', response.text)
        else:
            return CheckResult('EXTERNAL_IP', f"Unexpected status: {response.status_code}")
    except Exception as err:
        return CheckResult('EXTERNAL_IP', f"Exception: {err}")


def schedule_wrapper(database: Database, check_function: Callable[[], CheckResult]) -> Callable[[], None]:
    def wrapped_function():
        try:
            result = check_function()
            database.insert_check_result(result)
        except:
            logging.exception('Schedule job exception occurred')

    return wrapped_function


if __name__ == '__main__':
    logging.basicConfig(encoding='utf-8', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    database = Database()

    schedule.every(30).minutes.do(schedule_wrapper(database, external_ip_check))

    logging.info(f"Starting scheduler loop")
    while True:
        schedule.run_pending()
        time.sleep(1)
