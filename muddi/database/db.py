import sqlite3

users = """ 
    CREATE TABLE IF NOT EXISTS users (
        user_id integer PRIMARY KEY,
        name text NOT NULL,
        discord_tag text UNIQUE,
        discord_id integer UNIQUE,
        gender text,
        member_type text
    )
    """

# specific training
trainings = """ 
    CREATE TABLE IF NOT EXISTS trainings (
        training_id integer PRIMARY KEY,
        start timestamp NOT NULL,
        coach integer,
        description text,
        cancelled integer DEFAULT 0,
        schedule_id integer,
        FOREIGN KEY (schedule_id) REFERENCES schedule (schedule_id)
    )
    """

# for regular training schedules
schedule = """ 
    CREATE TABLE IF NOT EXISTS schedule (
        schedule_id integer PRIMARY KEY,
        weekday integer NOT NULL,
        hours integer NOT NULL,
        minutes integer NOT NULL,
        coach integer,
        description text
    )
    """

participants = """ 
    CREATE TABLE IF NOT EXISTS participants (
        user_id integer NOT NULL,
        training_id integer NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        FOREIGN KEY (training_id) REFERENCES trainings (training_id)
    )
    """


class DB:
    def __init__(self, database='muddi.db'):
        self.database = database
        conn = None
        try:
            conn = self.connect()
            c = conn.cursor()
            # create all tables if not exist
            for table in [users, trainings, schedule, participants]:
                c.execute(table)
        except sqlite3.Error as error:
            print(error)
        finally:
            if conn:
                conn.close()
    
    def connect(self):
        return sqlite3.connect(self.database, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)

    def commit(self, sql, parameters=None) -> bool:
        success = False
        conn = None
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute(sql) if not parameters else c.execute(sql, parameters)
            conn.commit()
            success = True
        except Exception as e:
            print(e)
            success = False
        finally:
            if conn:
                conn.close()
            return success

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