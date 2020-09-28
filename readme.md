Discord Bot für DMB - work in progress

# Setup
## requirements
- python 3.8
- you can find the required libs in the requirements.txt
## [set up gspread](https://gspread.readthedocs.io/en/latest/oauth2.html#for-bots-using-service-account)
## create google sheet
- you can lookup the header tests in spreadsheet_test.py for the header layout and run them to verify
## create Discord Application
- tutorial: https://discordpy.readthedocs.io/en/latest/discord.html
## create secrets.py file in the muddi directory (where main.py is)
Add the following variables with your own keys and id's
- `spreadsheet_key` - (str) the id of your google spread sheet with the needed tables
- `posting_channel` - (int) the ID of the channel where the bot is going to post the registration forms
- `managing_channel` - (int) the ID of the channel where the bot is going to accept commands
- `database_path` - (str) absolute path, including file name (.db ending) for the database
- `bot_token` - the developer credentials token for your discord application
# Run
