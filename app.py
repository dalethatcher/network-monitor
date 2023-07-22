import json
import logging
import queue
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Union, Dict

import requests
import schedule

ROOT = Path(__file__).parent
SQLITE_FILE = ROOT / 'monitor-db.sqlite'


class CheckResult:
    def __init__(self, check_type: str, success: bool, result: Dict[str, Union[str, int]]):
        self.at = datetime.now(timezone.utc)
        self.check_type = check_type
        self.success = success
        self.result = json.dumps(result)

    def __repr__(self):
        return str(self.__dict__)


class Database:
    def __init__(self):
        if not SQLITE_FILE.exists():
            self.__execute('PRAGMA ENCODING = UTF8')
            self.__execute(
                '''CREATE TABLE CHECK_LOG(
                       EVENT_ID INTEGER PRIMARY KEY,
                       AT TEXT, 
                       CHECK_TYPE TEXT,
                       SUCCESS INTEGER,
                       RESULT TEXT)''')

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
            self.__on_cursor(lambda c:
                             c.execute('INSERT INTO CHECK_LOG (AT, CHECK_TYPE, SUCCESS, RESULT) VALUES (?, ?, ?, ?)', [
                                 entry.at.isoformat().replace('+00:00', 'Z'),
                                 entry.check_type,
                                 1 if entry.success else 0,
                                 entry.result
                             ]))

    def insert_check_result(self, entry: CheckResult):
        self.entries.put(entry)


def external_ip_check() -> CheckResult:
    try:
        response = requests.get('https://api.ipify.org', timeout=5)

        if response.status_code == 200:
            return CheckResult('EXTERNAL_IP', True, {'ip': response.text})
        else:
            return CheckResult('EXTERNAL_IP', False, {'status_code': response.status_code})
    except Exception as err:
        logging.exception('Exception while resovling external ip')
        return CheckResult('EXTERNAL_IP', False, {'exception': str(err)})


def external_ping_check() -> CheckResult:
    try:
        process = subprocess.Popen(['ping', '-qc', '1', 'google.com'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(timeout=10)
        output = {'exit': process.returncode,
                  'stdout': stdout.decode('UTF-8'),
                  'stderr': stderr.decode('UTF-8')}

        return CheckResult('EXTERNAL_PING', process.returncode == 0, output)
    except Exception as err:
        logging.exception('Exception while pinging google.com')
        return CheckResult('EXTERNAL_PING', False, {'exception': str(err)})


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
    schedule.every(5).minutes.do(schedule_wrapper(database, external_ping_check))

    logging.info(f"Starting scheduler loop")
    while True:
        schedule.run_pending()
        time.sleep(1)
