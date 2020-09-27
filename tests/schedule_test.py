import unittest
from datetime import datetime

from muddi.models import Schedule


class TestSchedule(unittest.TestCase):

    def test_next_training(self):
        schedule = Schedule("Sunday", "18:00", "20:00",
                            "Jesus", "Fritzewiese", "BeSchrEibuNG", "Friday")
        training = schedule.next_training(datetime(2020, 9, 26))
        assert training.start == datetime(2020, 9, 27, 18, 0)
        assert training.end == datetime(2020, 9, 27, 20, 0)
        assert training.description == schedule.description
        assert training.coach == schedule.coach
        assert training.location == schedule.location


if __name__ == '__main__':
    unittest.main()