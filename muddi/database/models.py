from .db import DB
from datetime import date, timedelta, datetime


class User:
    def __init__(self, user_id, name, discord_tag="n/a", discord_id="n/a", gender="n/a", member_type="n/a"):
        self.user_id = user_id
        self.name = name
        self.discord_tag = discord_tag
        self.discord_id = discord_id
        self.gender = gender
        self.member_type = member_type

    def insert(self) -> bool:
        db = DB()
        sql = """ INSERT INTO users(name, discord_tag, discord_id, gender, member_type)
                  VALUES(?,?,?,?,?) """
        return db.commit(sql, (self.name, self.discord_tag, self.discord_id, self.gender, self.member_type))

    def remove(self):
        pass  # implementieren

    def update(self) -> bool:
        if not self.user_id:
            return False
        db = DB()
        sql = """ UPDATE users
                  SET name = ? ,
                      discord_tag = ? ,
                      discord_id = ? ,
                      gender = ? ,
                      member_type = ?"""
        db.commit(sql, (self.name, self.discord_tag, self.discord_id, self.gender, self.member_type))

    @classmethod
    def get_for_name(cls, name) -> list:
        db = DB()
        sql = """ SELECT * FROM users WHERE name=?"""
        data = db.select(sql, (name,))
        return [User(*x) for x in data]

    @classmethod
    def get_for_discord_id(cls, id):
        db = DB()
        sql = """ SELECT * FROM users WHERE discord_id=?"""
        return User(*db.select(sql, (id,))[0])

    @classmethod
    def get_all(cls):
        db = DB()
        sql = """ SELECT * FROM users """
        return [User(*x) for x in db.select(sql)]


class Schedule:
    """ Make sure that local time is set correctly! """
    def __init__(self, schedule_id, weekday, hours, minutes, coach, description):
        self.schedule_id = schedule_id
        self.weekday = weekday
        self.hours = hours
        self.minutes = minutes
        self.coach = coach
        self.description = description

    def insert(self):
        db = DB()
        sql = """ INSERT INTO schedule(weekday, hours, minutes, coach, description)
                  VALUES(?,?,?,?,?) """
        return db.commit(sql, (self.weekday, self.hours, self.minutes, self.coach, self.description))

    def remove(self):
        pass  # TODO: Implement


class Training:
    def __init__(self, training_id, start, coach, description="", cancelled=0, schedule_id=None):
        self.training_id = training_id
        self.start = start
        self.coach = coach
        self.description = description
        self.cancelled = cancelled
        self.schedule_id = schedule_id

    def insert(self):
        sql = """
            INSERT INTO trainings(start, coach, description, cancelled, schedule_id)
            VALUES(?,?,?,?,?)
            """
        db = DB()
        db.commit(sql, (self.start, self.coach, self.description, self.cancelled, self.schedule_id))

    def remove(self):
        pass  # TODO: Implement

    def cancel(self):
        pass  # TODO: Implement

    @classmethod
    def select_next_trainings(cls, day_offset=14):
        local_time = datetime.today()
        offset_time = local_time + timedelta(days=day_offset)
        sql = """
            SELECT * FROM trainings
            WHERE start > ? and start <= ?
            """
        db = DB()
        return [Training(*x) for x in db.select(sql, (local_time, offset_time))]

    def add_participant(self, user_id) -> bool:
        sql = """
            INSERT INTO participants(user_id, training_id)
            VALUES(?,?)
            """
        db = DB()
        return db.commit(sql, (user_id, self.training_id))

    def remove_participant(self, user_id) -> bool:
        sql = """
            DELETE FROM participants WHERE user_id=? AND training_id=?
            """
        db = DB()
        return db.commit(sql, (user_id, self.training_id))

    def participants(self) -> list:
        sql = """
            SELECT u.user_id, u.name, u.discord_tag, u.discord_id, u.gender, u.member_type
            FROM ( 
                users AS u
                INNER JOIN participants ON participants.user_id = u.user_id)
            INNER JOIN trainings ON participants.training_id = trainings.training_id
            WHERE trainings.training_id = ?
            """
        db = DB()
        return [User(*x) for x in db.select(sql, (self.training_id,))]


