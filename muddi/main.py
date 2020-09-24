import discord
from discord.ext import commands

muddi = commands.Bot(command_prefix='\\')
#  TODO: Commands

async def posting_routine(minutes=0, hours=1):
    #  check every once in a while if the next trainings should be postet
    #  decide if post once a week or 1 week before each training or something like that
    pass

if __name__ == '__main__':
    muddi.run()
    posting_routine()
    pass
