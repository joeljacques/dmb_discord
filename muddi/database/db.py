import sqlite3

from muddi.secrets import database_path

#  TODO handle multiple of the same discord tag/id
users = """ 
    CREATE TABLE IF NOT EXISTS users (
        user_id integer PRIMARY KEY,
        name text NOT NULL,
        discord_tag text,
        discord_id integer,
        gender text,
        member_type text
    )
    """

users_index = """
    CREATE INDEX IF NOT EXISTS idx_discord_id
    ON users (discord_id)
"""

# specific training
trainings = """
    CREATE TABLE IF NOT EXISTS trainings (
        training_id integer PRIMARY KEY,
        start timestamp NOT NULL,
        end timestamp NOT NULL,
        location text NOT NULL,
        coach integer,
        description text,
        cancelled integer DEFAULT 0,
        message_id integer UNIQUE
    )
    """

participants = """ 
    CREATE TABLE IF NOT EXISTS participants (
        user_id integer NOT NULL,
        training_id integer NOT NULL,
        noshow integer DEFAULT 0,
        FOREIGN KEY (user_id) 
            REFERENCES users (user_id)
            ON DELETE CASCADE,
        FOREIGN KEY (training_id) 
            REFERENCES trainings (training_id)
            ON DELETE CASCADE
    )
    """

participants_index = """
    CREATE INDEX IF NOT EXISTS participants_training_idx
    ON participants (user_id)
"""

setup_sql = [users, users_index, trainings, participants, participants_index]


class DB:
    def __init__(self, database=database_path):
        self.database = database

    def setup(self):
        conn = None
        try:
            conn = self.connect()
            c = conn.cursor()
            # create all tables if not exist
            for q in setup_sql:
                c.execute(q)
        except sqlite3.Error as error:
            print(error)
        finally:
            if conn:
                conn.close()

    def connect(self):
        return sqlite3.connect(self.database, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)

    def commit(self, sql, parameters=None, insert=False):
        result = None
        conn = None
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute(sql) if not parameters else c.execute(sql, parameters)
            conn.commit()
            result = c.lastrowid if insert else True
        except Exception as e:
            print(e)
            result = False
        finally:
            if conn:
                conn.close()
            return result

    def select(self, sql, parameters=None) -> list:
        data = []
        conn = None
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute(sql) if not parameters else c.execute(sql, parameters)
            data = c.fetchall()
        except Exception as e:
            print(e)
        finally:
            if conn:
                conn.close()
            return data

    def backup(self):
        pass  # TODO: Implementieren -> Als csv exportieren und in google sheet laden?

if __name__ == '__main__':
    DB()
