import gspread

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

gc = gspread.service_account()

class Spreadsheet:
    def __init__(self, title):
        self.sheet = gc.open(title)

