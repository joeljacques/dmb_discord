import gspread
from typing import Dict, List, Optional
from muddi import secrets
from muddi.utils.tools import valid_discord

# GOOGLESHEET KEY
schedule_key = secrets.schedule_key
club_key = secrets.club_key
# WORKSHEETS
#guests worksheet in the schedule spreadsheet
guests_title = "Guests"
# players worksheet in the club spreadsheet
players_title = "Spieler*innen-Infos"
# schedule worksheet in the schedule spreadsheet
schedules_title = "Schedules"
# HEADERS
# schedule
day = "Weekday"
start = "Start time"
end = "End time"
coach = "Coach"
location = "Location"
description = "Description"
notification = "Notification Day"
# players
u_name = "Name"
discord_tag = "Discord Tag"
member_type = "Status"
GUEST = "Gast"
EICHE = "TVE-Mitglied"
UNI = "Hospo"
gender = "m/w/d"



def _valid_time(string: str) -> bool:
    if len(splt := string.split(":")) == 2:
        return all(map(lambda x: x.isnumeric(), splt)) and 0 <= int(splt[0]) <= 23 and 0 <= int(splt[1]) <= 60
    

class Spreadsheet: #  TODO: Optimize by not connecting to BOTH sheets on initialization (use @property?)
    def __init__(self, schedule=schedule_key, club=club_key, players=players_title, guests=guests_title,
                 schedules=schedules_title, user_max_rows=100, schedule_max_rows=100):
        gc = gspread.service_account()
        self.user_max_rows = user_max_rows
        self.schedule_max_rows = schedule_max_rows
        schedule_sheet = gc.open_by_key(schedule)
        club_sheet = gc.open_by_key(club)
        self.guests = schedule_sheet.worksheet(guests)
        self.players = club_sheet.worksheet(players)
        self.schedules: gspread.Worksheet = schedule_sheet.worksheet(schedules)

    def get_schedules(self):
        """
        Fetches all valid Schedule rows from the 'Schedules' worksheet as dictionaries
        :rtype: list
        """
        schedules = self.schedules.get_all_records(head=2)
        # only rows with weekday, start time, end time, location and notification day are valid
        return list(filter(lambda r: all([r[notification], r[day], _valid_time(r[start]),
                                          _valid_time(r[end]), r[location]]), schedules))

    def get_users(self) -> List[Dict[str, str]]:
        """
        Fetches all valid rows from the 'Names' worksheet as dicitionaries. Valid rows have a value in the name column.
        :return:
        """
        guests = self.guests.get_all_records(head=2)
        players = self.players.get_all_records(head=2)
        players.extend(guests)

        # filter out duplicates by discord tag
        filtered_dicts = {}
        no_tag = []
        for d in players:
            if not valid_discord(d[discord_tag]):
                d[discord_tag] = ""
                no_tag.append(d)
            elif d[discord_tag] not in filtered_dicts.keys():
                filtered_dicts[d[discord_tag]] = d

        users = list(filtered_dicts.values())
        users.extend(no_tag)


        # only rows with a name are valid
        return list(filter(lambda r: all([r[u_name]]), users))

    def get_guest_at_row(self, row_id) -> Optional[Dict[str, str]]:
        """
        :rtype: Dict[str, str] The row of the user spreadsheet for the given id, None if name is empty
        """
        if not 0 < row_id <= self.user_max_rows:
            return None
        rows = self.guests.batch_get([f"A{row_id}:D{row_id}", "A2:D2"])
        user = {headers: value for value, headers in zip(rows[0][0], rows[1][0])}
        return user if user[u_name] else None


    def get_discord_users(self):
        """Gets all users that have a name, discord tag and gender"""
        list(filter(lambda r: r[discord_tag], self.get_users()))




