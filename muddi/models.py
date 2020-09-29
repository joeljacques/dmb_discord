from datetime import timedelta, datetime, time
from time import strptime, struct_time
from typing import List, Dict
from discord import Member

import muddi.spreadsheet as sh
from muddi.database.db import DB
from muddi.spreadsheet import Spreadsheet
from muddi.utils.tools import valid_discord


class User:
    def __init__(self, user_id, name, discord_tag="", discord_id="", gender="n/a", member_type="n/a"):
        self.user_id: int = user_id
        self.name: str = name
        self.discord_tag: str = discord_tag
        self.discord_id: int = discord_id
        self.gender: str = gender
        self.member_type: str = member_type

    def __str__(self):
        return f"User: {self.name}, ID: {self.user_id}, Discord: {self.discord_tag}, Gender: {self.gender}, Member: {self.member_type}"

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
                      member_type = ?
                    WHERE user_id = ? """
        db.commit(sql, (self.name, self.discord_tag, self.discord_id, self.gender, self.member_type, self.user_id))

    @classmethod
    def update_from_sheet(cls):
        """ Synchronizes the google sheet with the database """
        sheet = Spreadsheet()
        rows = sheet.get_users()
        users = User.get_all()
        u_tags = dict(list(map(lambda usr: (usr.discord_tag, usr), users)))
        u_names = dict(list(map(lambda usr: (usr.name, usr), users)))
        for r in rows:
            rtag = r[sh.discord_tag].strip("@")
            rname = r[sh.u_name]
            rgender = r[sh.gender]
            rmember_type = r[sh.member_type]
            if rtag and valid_discord(rtag) and rtag not in u_tags.keys():
                User(None, rname, discord_tag=rtag, gender=r[sh.gender], member_type=r[sh.member_type]).insert()
            elif (valid := (valid_discord(rtag))) or rname in u_names.keys():
                user = u_tags[rtag] if valid else u_names[rname]
                edited = False
                if user.name != rname:
                    edited = True
                    user.name = rname
                if user.gender != rgender:
                    edited = True
                    user.gender = rgender
                if user.member_type != rmember_type:
                    edited = True
                    user.member_type = rmember_type
                if user.discord_tag != rtag and valid_discord(rtag):
                    edited = True
                    user.discord_tag = rtag
                if edited:
                    user.update()
            elif rname and rname not in u_names.keys():
                User(None, rname, gender=rgender, member_type=rmember_type).insert()

    @classmethod
    def update_from_discord_members(cls, members: List[Member]):
        all_users = User.get_all()
        ids = list(map(lambda u: u.discord_id, all_users))
        member_tags: Dict[str, Member] = dict(map(lambda m: (str(m), m), members))
        member_ids: Dict[int, Member] = dict(map(lambda m: (m.id, m), members))
        for user in all_users:
            utag = user.discord_tag
            uid = user.discord_id
            # add discord id if not in database
            if utag in member_tags.keys() and not user.discord_id:
                user.discord_id = member_tags[utag].id
                user.update()
                ids.append(user.discord_id)
            # update discord tag if changed TODO: will lead to new user being added if old discord tag is still in sheet
            elif uid in member_ids.keys() and utag != (tag := str(member_ids[uid])):
                user.discord_tag = tag
                user.update()
        remaining: List[Member] = list(filter(lambda m: m.id not in ids, members))
        for member in remaining:
            User(None, name=member.display_name, discord_tag=str(member), discord_id=member.id).insert()

    @classmethod
    def sync(cls, members: List[Member]):
        User.update_from_sheet()
        User.update_from_discord_members(members)

    @classmethod
    def get_guest_for_name(cls, name):
        db = DB()
        sql = """ SELECT * FROM users WHERE name=? AND member_type=?"""
        data = db.select(sql, (name, sh.GUEST))
        return User(*data[0]) if data else None

    @classmethod
    def get_for_discord_id_or_tag(cls, discord_id, discord_tag=None):
        db = DB()
        sql = """ SELECT * FROM users WHERE discord_id=? OR discord_tag=? """
        ls = db.select(sql, (discord_id, discord_tag))
        return User(*ls[0]) if ls else None  # todo change to all results?

    @classmethod
    def get_for_id(cls, user_id):
        db = DB()
        sql = """ SELECT * FROM users WHERE user_id=?"""
        return User(*db.select(sql, (user_id,))[0])

    @classmethod
    def get_all(cls):
        db = DB()
        sql = """ SELECT * FROM users """
        return [User(*x) for x in db.select(sql)]


class Schedule:
    """ Make sure that local time is set correctly! """
    def __init__(self, weekday, start: str, end: str, coach, location, description, notification):
        self.weekday: str = weekday
        self.start: struct_time = strptime(start, "%H:%M")
        self.end: struct_time = strptime(end, "%H:%M")
        self.coach = coach
        self.location = location
        self.description = description
        self.notification = notification

    def insert(self):
        raise NotImplementedError

    def weekdayint(self, day=None):
        day = day or self.weekday
        return {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                "Friday": 4, "Saturday": 5, "Sunday": 6}[day]

    def next_notification(self, reference: datetime = datetime.today()):
        week_before = self.next_training(reference).start.date() - timedelta(days=7)
        day_diff = (self.weekdayint(self.notification) - week_before.weekday()) % 7
        return week_before + timedelta(days=day_diff)

    def next_training(self, reference: datetime = datetime.today()):
        """
        Create the next Training instance of this Schedule of the coming 7 days, including today
        :return:
        """
        day_diff = (self.weekdayint() - reference.weekday()) % 7
        stime, etime = tuple([time(hour=x.tm_hour, minute=x.tm_min) for x in [self.start, self.end]])
        stime, etime = tuple([datetime.combine(reference + timedelta(days=day_diff), x) for x in [stime, etime]])

        return Training(None, stime, etime, self.location, self.coach, self.description)

    def scheduled(self):
        """checks if a training within the next 7 days for this schedule has been created"""
        nt = self.next_training()
        result = None
        try:
            db = DB()
            sql = """
            SELECT * FROM trainings
            WHERE start = ? AND end = ? AND location = ? """
            trainings = db.select(sql, (nt.start, nt.end, nt.location))
            if trainings:
                result = Training(*trainings[0])
            else:
                result = None
        except Exception as e:
            print("Error when executing Schedule.scheduled()!")
        finally:
            return result

    def remove(self):
        raise NotImplementedError

    @classmethod
    def get_schedules(cls):
        sheet = Spreadsheet()
        rows = sheet.get_schedules()
        return [Schedule(r[sh.day], r[sh.start], r[sh.end], r[sh.coach], r[sh.location],
                         r[sh.description], r[sh.notification]) for r in rows]


class Training:
    def __init__(self, training_id, start, end, location, coach, description="", cancelled=0, message_id=None):
        self.training_id = training_id
        self.start: datetime = start
        self.end: datetime = end
        self.location = location
        self.coach = coach
        self.description = description
        self.cancelled = cancelled
        self.message_id = message_id
        self._participants = None

    def insert(self):
        if (not self.message_id) or self.training_id:
            print("Can't insert training without message_id or with training_id!")
            return False
        try:
            sql = """
            INSERT INTO trainings(start, end, location, coach, description, cancelled, message_id)
            VALUES(?,?,?,?,?,?,?)
            """
            db = DB()
            return db.commit(sql, (self.start, self.end, self.location, self.coach, self.description,
                        self.cancelled, self.message_id), insert=True)
        except Exception as e:
            print("couldn't insert")

    def update(self):
        if self.training_id:
            set = lambda x: f"{x} = ?"
            db = DB()
            sql = """
                UPDATE trainings
                SET start = ? ,
                    end = ? ,
                    location = ? ,
                    coach = ? ,
                    description = ? ,
                    cancelled = ?,
                    message_id = ? 
                WHERE training_id = ?"""
            db.commit(sql, (self.start, self.end, self.location, self.coach,
                            self.description, self.cancelled, self.message_id, self.training_id))

    def remove(self):
        pass  # TODO: Implement

    @classmethod
    def get_for_id(cls, training_id):
        sql = """
        SELECT * from trainings
        WHERE training_id = ?"""
        db = DB()
        result = db.select(sql, (training_id,))
        return Training(*result[0]) if result else None

    @classmethod
    def get_for_message_ids(cls, ids: List[int]):
        # make list distinct
        ids = set(ids)
        result = []
        if ids:
            sql = f"""
                SELECT * from trainings 
                WHERE message_id in ({','.join(['?'] * len(ids))})"""
            db = DB()
            result = db.select(sql, tuple(ids))
        return [Training(*r) for r in result]

    @classmethod
    def select_next_trainings(cls, day_offset=7, reference=datetime.today(), include_cancelled=False):
        offset_time = reference + timedelta(days=day_offset)
        sql = """
            SELECT * FROM trainings
            WHERE start > ? and start <= ?
            """ if include_cancelled else """ SELECT * FROM trainings Where start > ? and start <= ? and cancelled = 0"""
        db = DB()
        return [Training(*x) for x in db.select(sql, (reference, offset_time, ))]

    def add_participant(self, user_id) -> bool:
        sql = """
            INSERT INTO participants(user_id, training_id)
            VALUES(?,?)
            """
        db = DB()
        if self.participants:
            self._participants.append(User.get_for_id(user_id))  # ugly?
        else:
            self._participants = [(User.get_for_id(user_id))]
        return db.commit(sql, (user_id, self.training_id))

    def remove_participant(self, user_id) -> bool:
        sql = """
            DELETE FROM participants WHERE user_id=? AND training_id=?
            """
        db = DB()
        if self.participants:
            self._participants = list(filter(lambda u: u.user_id != user_id,self._participants))  # ugly?
        else:
            self._participants = []
        return db.commit(sql, (user_id, self.training_id))

    def remove_guest_participant(self, name: str) -> bool:
        guest = User.get_guest_for_name(name)
        return self.remove_participant(guest.user_id) if guest else False

    def no_show(self, user_id):
        if not next((usr for usr in self.participants if u.user_id == user_id), False):
            return False
        else:
            sql = """
                UPDATE participants
                SET no_show = 1
                WHERE training_id = ? AND user_id = ?"""
            db = DB()
            return db.commit(sql, (self.training_id, user_id))

    @property
    def participants(self) -> [User]:
        if not self._participants:
            sql = """
            SELECT u.user_id, u.name, u.discord_tag, u.discord_id, u.gender, u.member_type
            FROM ( 
                users AS u
                INNER JOIN participants ON participants.user_id = u.user_id)
            INNER JOIN trainings ON participants.training_id = trainings.training_id
            WHERE trainings.training_id = ?
            """
            db = DB()
            self._participants = [User(*x) for x in db.select(sql, (self.training_id,))]
        return self._participants


if __name__ == '__main__':
    User.update_from_sheet()
    users = User.get_all()
    for u in users:
        print(u)
