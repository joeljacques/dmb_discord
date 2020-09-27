import discord

from muddi import secrets
from muddi.database.bot import Muddi
from muddi.database.db import DB
from muddi.models import User

DB().setup()
muddi = Muddi(command_prefix='\\')

@muddi.event
async def on_ready():
    guild: discord.Guild = muddi.guilds[0]
    print(guild.id)
    muddi.guild = guild
    User.sync(guild.members)
    muddi.posting_channel = guild.get_channel(secrets.posting_channel)
    muddi.managing_channel = guild.get_channel(secrets.managing_channel)
    print("Logged in as")
    print(muddi.user.name)
    print(muddi.user.id)
    print('--------')

@muddi.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    if str(reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.trainings.keys() and reaction.user_id != muddi.user.id:
        training = muddi.trainings[reaction.message_id]
        if not reaction.user_id in muddi.user_ids.keys():
            User.update_from_discord_members(muddi.guild.members)
        training.add_participant(muddi.user_ids[reaction.user_id].user_id)
        message = await muddi.posting_channel.fetch_message(reaction.message_id)

        await message.edit(embed=muddi.posting_embed(
            training, [(u.name, muddi.guild.get_member(u.discord_id).mention, u.gender) for u in training.participants]))

@muddi.event
async def on_raw_reaction_remove(reaction: discord.RawReactionActionEvent):
    if str(reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.trainings.keys() and reaction.user_id != muddi.user.id:
        training = muddi.trainings[reaction.message_id]
        training.remove_participant(muddi.user_ids[reaction.user_id].user_id)
        message = await muddi.posting_channel.fetch_message(reaction.message_id)

        await message.edit(embed=muddi.posting_embed(
            training, [(u.name, muddi.guild.get_member(u.discord_id).mention, u.gender) for u in training.participants]))



#  TODO: Commands

muddi.run(secrets.bot_token)
