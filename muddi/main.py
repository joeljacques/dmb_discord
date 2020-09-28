import discord
from discord.ext import commands
from muddi import secrets
from muddi.bot import Muddi
from muddi.database.db import DB
from muddi.models import User, Training
from muddi import spreadsheet as sh
from copy import deepcopy
import tempfile

from muddi.utils.embeds import cancel_embed, posting_embed

DB().setup()
muddi = Muddi(command_prefix='.')


@muddi.event
async def on_ready():
    guild: discord.Guild = muddi.get_guild(secrets.guild_id)
    muddi.guild = guild
    muddi.posting_channel = guild.get_channel(secrets.posting_channel)
    muddi.managing_channel = guild.get_channel(secrets.managing_channel)
    print("Logged in as")
    print(muddi.user.name)
    print(muddi.user.id)
    print('--------')
    muddi.schedule_loop.start()

@muddi.event
async def on_member_join(member: discord.Member):
    if member.guild.id == muddi.guild.id:
        if not User.get_for_discord_id_or_tag(member.id, str(member)):
            User(None, member.display_name, str(member), member.id).insert()

@muddi.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if str(reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.trainings.keys() and reaction.user_id != muddi.user.id:
        training = muddi.trainings[reaction.message_id]
        if training.cancelled:
            return
        if reaction.user_id not in muddi.user_ids.keys():
            User.update_from_discord_members(muddi.guild.members)
        training.add_participant(muddi.user_ids[reaction.user_id].user_id)
        tr = deepcopy(training)
        muddi.trainings_lock.release()
        await update_training_post(training)
    else:
        muddi.trainings_lock.release()


@muddi.event
async def on_raw_reaction_remove(reaction: discord.RawReactionActionEvent):
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if str(
            reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.trainings.keys() and reaction.user_id != muddi.user.id:
        training = muddi.trainings[reaction.message_id]
        if training.cancelled:
            return
        training.remove_participant(muddi.user_ids[reaction.user_id].user_id)
        tr = deepcopy(training)
        muddi.trainings_lock.release()
        await update_training_post(tr)
    else:
        muddi.trainings_lock.release()


def check_channel(ctx: commands.Context):
    return ctx.channel.id == secrets.managing_channel


@muddi.group(name="training")
@commands.check(check_channel)
async def _training(ctx):
    """ Command for all things related organization of trainings."""
    if ctx.invoked_subcommand is None:
        await ctx.send("Enter `help` to learn how to use `training`")

@_training.command()
async def active(ctx):
    """ Active training posts from today to next week"""
    tr = Training.select_next_trainings()
    embed = discord.Embed(title="Posted trainings of today and the next week")
    fmt = "%A, %d. %b %Y %H:%Mh"
    for t in tr:
        message = await muddi.posting_channel.fetch_message(t.message_id)
        embed.add_field(name=f"{t.start.strftime(fmt)} {t.location} with {t.coach}"
                             f" - currently {len(t.participants)} participants", value=message.jump_url)
    await ctx.send(embed=embed)


@_training.command(name="csv")
async def training_csv(ctx: commands.Context, training_id):
    f""" type `{muddi.command_prefix}` csv {{training id}} to receive a participants csv. """
    if not muddi.trainings_lock.acquire():
        print("Couldn't acquire trainings lock")
        return

    def quotes(x):
        return f"\"{x}\""

    if training := Training.get_for_id(training_id):
        participants = deepcopy(training.participants)
        filename = f"{training.start.strftime('%Y-%m-%d-%H-%M')}-" \
                   f"{training.location}{'-' + training.coach if training.coach else ''}" \
                   f"{'-cancelled' if training.cancelled else ''}.csv"
        muddi.trainings_lock.release()
        tf = tempfile.NamedTemporaryFile()
        tf.write("name,member type\n".encode('UTF-8'))
        tf.writelines((",".join([quotes(u.name), quotes(u.member_type)]) + "\n").encode('UTF-8') for u in participants)
        tf.flush()
        with open(tf.name, 'rb') as file:
            await ctx.author.send(content="here's your file", file=discord.File(file, filename=filename))
        tf.close()
    else:
        muddi.trainings_lock.release()


@_training.command(name="no-show")
@commands.check(check_channel)
async def no_show(ctx, training_id, user_tag):
    f""" type `{muddi.command_prefix}training no-show {{training id}} {{discord_tag}}` to mark the user as no-show."""
    try:
        user_tag = str(await commands.MemberConverter().convert(ctx, user_tag))
        if not muddi.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        if tr := next((tr for tr in muddi.trainings.values() if tr.training_id == training_id), None):
            if usr := next((u for u in tr.participants if u.discord_tag == user_tag)):
                tr.no_show(usr.user_id)
    except commands.BadArgument as e:
        await ctx.send(content="Invalid tag!")
        return
    except commands.CommandError:
        await ctx.send(content="Something went wrong! Try again or contact admin.")
        return
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if tr := next((tr for tr in muddi.trainings.values() if tr.training_id == training_id), None):
        if usr := next((u for u in tr.participants if u.discord_tag == user_tag)):
            tr.no_show(usr.user_id)
    muddi.trainings_lock.release()


@_training.command()
async def cancel(ctx: commands.Context, training_id: int):
    f""" type `{muddi.command_prefix}training cancel {{training id}}` to cancel a training that has been posted and
has not ended more than 23 hours ago"""
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if tr := next((tr for tr in muddi.trainings.values() if tr.training_id == training_id), None):
        tr.cancelled = 1
        tr.update()
        message_id = tr.message_id
        embed = cancel_embed(tr)
        discord_tags = [f"@{p.discord_tag}" for p in tr.participants if p.discord_tag]
        muddi.trainings_lock.release()
        post = await muddi.posting_channel.fetch_message(message_id)
        await post.edit(embed=embed)
        await ctx.send(f"Training cancelled. Use ```{' '.join(discord_tags)}``` "
                       f"to notify all participants (except guests).")
    else:
        muddi.trainings_lock.release()

@_training.command()
async def uncancel(ctx: commands.Context, training_id: int):
    """ Reactivates the training instance """
    if tr := Training.get_for_id(training_id):
        if not muddi.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        tr.cancelled = 0
        tr.update()
        muddi.trainings[tr.message_id] = tr
        tr = deepcopy(tr)
        muddi.trainings_lock.release()
        await update_training_post(tr)


@_training.group("set")
async def training_set(ctx):
    """ Use to change coach, location or description"""

async def training_set_attribute(ctx, training_id: int, attr: str, new_value):
    training = Training.get_for_id(training_id)
    if not training:
        await ctx.send(content=f"Training with ID {training_id} doesn't exist!")
        return
    setattr(training, attr, new_value)
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire lock!")
        return
    if any(tr.training_id == training.training_id for tr in muddi.trainings.values()):
        muddi.trainings[training.message_id] = training
        training.update()
    training = deepcopy(training)
    muddi.trainings_lock.release()
    await update_training_post(training)
    await ctx.send(content="Successfully changed training!")

@training_set.command("coach")
async def training_set_coach(ctx, training_id: int, coach: str):
    await training_set_attribute(ctx, training_id=training_id, attr="coach", new_value=coach)


@training_set.command("location")
async def training_set_location(ctx, training_id: int, location: str):
    await training_set_attribute(ctx, training_id=training_id, attr="location", new_value=location)

@training_set.command("description")
async def training_set_description(ctx, training_id: int, description: str):
    """ Put the description in quotes """
    await training_set_attribute(ctx, training_id=training_id, attr="description", new_value=description)

@_training.group("add")
async def training_add(ctx):
    f""" type `{muddi.command_prefix}training add guest {{training id}} {{spreadsheet id}}`
    to add a guest to the list. The spreadsheet id is the row number taken from 
    https://docs.google.com/spreadsheets/d/1EBDeTRijlMmmbAiXnrs05RyveKYRahykTnVJ4x1RMG4/edit?usp=sharing"""
    if ctx.invoked_subcommand is None:
        await ctx.send("Use `training add guest \{training id\} \{spreadsheet id\} to add a guest")


@_training.group("remove")
async def training_remove(ctx):
    f""" type `{muddi.command_prefix}training remove guest {{training id}} {{guest name}}`
    to remove a guest from the participants list. The name is the displayed name in the participants list."""
    if ctx.invoked_subcommand is None:
        await ctx.send("Use `training add guest \{training id\} {{guest name}} to remove")


@training_add.command(name="guest")
async def add_guest(ctx, training_id: int, guest_rowid: int):
    f""" type `{muddi.command_prefix}training add guest {{training id}} {{spreadsheet id}}`
    to add a guest to the list. The spreadsheet id is the row number taken from 
    https://docs.google.com/spreadsheets/d/1EBDeTRijlMmmbAiXnrs05RyveKYRahykTnVJ4x1RMG4/edit?usp=sharing"""
    sheet = sh.Spreadsheet()
    if not (guest_row := sheet.get_user_at_row(row_id=guest_rowid)) or guest_row[sh.member_type] != sh.GUEST:
        await ctx.send(content="The referenced row isn't a valid guest entry!")
        return
    tr: Training = Training.get_for_id(training_id)
    if not tr:
        await ctx.send(content=f"Training: with ID {training_id} not found!")
    else:
        # check if guest is in database
        user = User.get_guest_for_name(guest_row[sh.u_name])
        if not user:
            User.update_from_sheet()
            user = User.get_guest_for_name(guest_row[sh.u_name])[0]
        if user.name in [p.name for p in tr.participants]:
            await ctx.send(content=f"This person is already a participant!")
            return
        success = tr.add_participant(user_id=user.user_id)
        if not success:
            await ctx.send(content=f"Something went wrong when trying to add participant to training #{training_id}")
            return
        if not muddi.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        if tr.message_id in muddi.trainings.keys():
            muddi.trainings[tr.message_id] = tr
        tr_copy = deepcopy(tr)  # sacrificing a bit space for potentially more speed
        muddi.trainings_lock.release()
        await update_training_post(tr_copy)


@training_remove.command(name="guest")
async def remove_guest(ctx: commands.Context, training_id: int, name: str):
    f""" type `{muddi.command_prefix}training remove guest {{training id}} {{guest name}}`
    to remove a guest from the participants list. The name is the displayed name in the participants list."""
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    for tr in muddi.trainings.values():
        if tr.training_id == training_id:
            for p in tr.participants:
                if p.member_type == sh.GUEST and p.name == name:
                    if tr.remove_participant(p.user_id):
                        trcopy = deepcopy(tr)
                        muddi.trainings_lock.release()
                        await update_training_post(deepcopy(trcopy))
                        await ctx.send(content=f"Successfully removed {name} from training #{training_id}")
                        return
    muddi.trainings_lock.release()
    past_training = Training.get_for_id(training_id)
    if past_training:
        if past_training.remove_guest_participant(name):
            await update_training_post(past_training)
            await ctx.send(content=f"Successfully removed {name} from training #{training_id}")



async def update_training_post(training: Training):
    message = await muddi.posting_channel.fetch_message(training.message_id)
    await message.edit(embed=posting_embed(
        training, [(u.name, mem.mention if (mem := muddi.guild.get_member(u.discord_id)) else "(Guest)",
                    u.gender) for u in training.participants], muddi.add_emoji))


async def remove_guest_name(training: Training, name: str):
    for p in training.participants:
        if p.name.lower() == name.lower() and p.member_type == sh.GUEST:
            training.remove_participant(p.user_id)


#  TODO: Commands

muddi.run(secrets.bot_token)
