import sqlite3
import datetime
from os.path import expanduser
from typing import Iterable, List

from prompt_toolkit.history import History

from peek.config import config_location, ensure_dir_exists


class SqLiteHistory(History):

    def __init__(self):
        super().__init__()
        db_file = expanduser(config_location() + 'history')
        ensure_dir_exists(db_file)
        self.conn = sqlite3.connect(db_file)
        self.conn.execute('CREATE TABLE IF NOT EXISTS history '
                          '(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, timestamp INTEGER NOT NULL)')
        self.conn.commit()

    def __del__(self):
        self.conn.close()

    def load_history_strings(self) -> Iterable[str]:
        strings: List[str] = []
        for row in self.conn.execute('SELECT * FROM history ORDER BY id DESC LIMIT 1000'):
            strings.append(row[1])
        return strings

    def store_string(self, string: str) -> None:
        self.conn.execute("INSERT INTO history(content, timestamp) VALUES (?, ?)", (string, datetime.datetime.now()))
        self.conn.commit()
