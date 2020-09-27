import unittest

import muddi.spreadsheet as sh
from muddi.spreadsheet import Spreadsheet


class TestSpreadsheet(unittest.TestCase):
    def setUp(self):
        self.sheet = Spreadsheet()

    def test_schedule_headers(self):
        headers = self.sheet.schedules.row_values(1)[:7]
        assert headers == [sh.day, sh.start, sh.end, sh.coach, sh.location, sh.description, sh.notification]

    def test_user_headers(self):
        assert self.sheet.users.row_values(1)[:4] == [sh.u_name, sh.discord_tag, sh.member_type, sh.gender]


if __name__ == '__main__':
    unittest.main()
