import gspread

from muddi import secrets

# GOOGLESHEET KEY
sheet_key = secrets.spreadsheet_key
# WORKSHEETS
users_title = "Names"
schedules_title = "Schedules"
# HEADERS
day = "Weekday"
start = "Start time"
end = "End time"
coach = "Coach"
location = "Location"
description = "Description"
notification = "Notification Day"
u_name = "Name"
discord_tag = "Discord"
member_type = "Membership"
gender = "Gender"



def _valid_time(string: str) -> bool:
    if len(splt := string.split(":")) == 2:
        return all(map(lambda x: x.isnumeric(), splt)) and 0 <= int(splt[0]) <= 23 and 0 <= int(splt[1]) <= 60


class Spreadsheet:
    def __init__(self, key=sheet_key, users=users_title, schedules=schedules_title):
        gc = gspread.service_account()
        self.sheet = gc.open_by_key(key)
        self.users = self.sheet.worksheet(users)
        self.schedules: gspread.Worksheet = self.sheet.worksheet(schedules)

    def get_schedules(self):
        """
        Fetches all valid Schedule rows from the 'Schedules' worksheet as dictionaries
        :rtype: list
        """
        all_rows = self.schedules.get_all_values()
        column_names = all_rows[0]
        all_rows = [{column: value for (column, value) in zip(column_names, row)} for row in all_rows[1:]]
        # only rows with weekday, start time, end time, location and notification day are valid
        return list(filter(lambda r: all([r[notification], r[day], _valid_time(r[start]),
                                              _valid_time(r[end]), r[location]]), all_rows))

    def get_users(self):
        """
        Fetches all valid rows from the 'Names' worksheet as dicitionaries
        :return:
        """
        all_rows = self.users.get("A1:D100")
        column_names = all_rows[0]
        all_rows = [{column: value for (column, value) in zip(column_names, row)} for row in all_rows[1:]]
        # only rows with a name are valid
        return list(filter(lambda r: all([r[u_name], r[gender]]), all_rows))

    def get_discord_users(self):
        """Gets all users that have a name, discord tag and gender"""
        list(filter(lambda r: r[discord_tag], self.get_users()))




