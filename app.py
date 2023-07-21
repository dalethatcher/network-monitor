import queue
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).parent
SQLITE_FILE = ROOT / 'monitor-db.sqlite'


class Database:
    def __init__(self):
        if not SQLITE_FILE.exists():
            self.__execute('''CREATE TABLE CHECK_LOG(
                EVENT_ID INTEGER PRIMARY KEY, AT TEXT, TYPE TEXT, RESULT TEXT)''')

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
            entry = self.entries.get()
            self.__on_cursor(lambda c: c.execute('INSERT INTO CHECK_LOG (AT, TYPE, RESULT) VALUES (?, ?, ?)', entry))

    def insert_entry(self, at: datetime, type: str, result: str):
        self.entries.put([at.isoformat().replace('+00:00', 'Z'), type, result])


if __name__ == '__main__':
    database = Database()

    database.insert_entry(datetime.now(timezone.utc), 'test', 'result')

    time.sleep(1)
