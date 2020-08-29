import datetime
import sqlite3
from os.path import expanduser
from typing import Iterable, List

from prompt_toolkit.history import History

from peek.config import config_location, ensure_dir_exists

HIST_MAX = 10_000


class SqLiteHistory(History):

    def __init__(self, history_max=HIST_MAX):
        super().__init__()
        self.history_max = history_max
        db_file = expanduser(config_location() + 'history')
        ensure_dir_exists(db_file)
        self.conn = sqlite3.connect(db_file)
        self.conn.execute('CREATE TABLE IF NOT EXISTS history '
                          '(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, timestamp INTEGER NOT NULL)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS connection '
                          '(name TEXT PRIMARY KEY, data TEXT NOT NULL, timestamp INTEGER NOT NULL)')
        self._maintain_size()
        self.conn.commit()

    def __del__(self):
        self.conn.close()

    def _maintain_size(self):
        c = self.conn.cursor()
        res = c.execute('SELECT COUNT(*) from history').fetchone()
        if res is None or res[0] < self.history_max:
            return
        c.execute('DELETE FROM history where id in (SELECT id FROM history ORDER BY id limit ?)',
                  (res[0] - self.history_max,))

    def load_history_strings(self) -> Iterable[str]:
        strings: List[str] = []
        for row in self.conn.execute('SELECT * FROM history ORDER BY id DESC'):
            strings.append(row[1])
        return strings

    def store_string(self, string: str) -> None:
        self.conn.execute("INSERT INTO history(content, timestamp) VALUES (?, ?)", (string, datetime.datetime.now()))
        self.conn.commit()

    def load_recent(self, size=100):
        lines = []
        for row in self.conn.execute("select * from history where id > (select max(id) from history) - ?", (size,)):
            lines.append((row[0], row[1]))
        return lines

    def get_entry(self, index):
        if index > 0:
            for row in self.conn.execute('select * from history where id = ?', (index,)):
                return row[0], row[1]
            else:
                return None
        elif index < 0:
            for row in self.conn.execute('select * from history where id = (select max(id) from history) + ?',
                                         (index,)):
                return row[0], row[1]
            else:
                return None
        else:
            return None

    def save_session(self, name, data):
        self.conn.execute("INSERT INTO connection(name, data, timestamp) VALUES(?, ?, ?) "
                          "ON CONFLICT (name) DO UPDATE SET data=excluded.data, timestamp=excluded.timestamp",
                          (name, data, datetime.datetime.now()))
        self.conn.commit()

    def load_session(self, name):
        for row in self.conn.execute("SELECT data FROM connection WHERE name = ?", (name,)):
            return row[0]
        else:
            return None

    def list_sessions(self):
        return list(self.conn.execute("SELECT name, timestamp FROM connection"))

    def clear_sessions(self):
        self.conn.execute("DELETE FROM connection")

    def delete_session(self, name):
        return self.conn.execute("DELETE FROM connection where name = ?", (name,)).rowcount == 1
