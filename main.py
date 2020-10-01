import discord
from discord.ext import commands
from muddi import secrets
from muddi.bot import Muddi
from muddi.database.db import DB
from muddi.models import User, Training
from muddi import spreadsheet as sh
from copy import deepcopy
from datetime import datetime
import tempfile
from muddi.utils.embeds import cancel_embed, posting_embed

DB().setup()
muddi = Muddi(command_prefix='.',)


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
        User.sync(muddi.guild.members)

@muddi.event
async def on_message_delete(message: discord.Message):
    if message.id in muddi.message_ids:
        training = Training.get_for_message_ids([message.id])[0]
        if not training.cancelled:
            training_id = training.training_id
            await muddi.managing_channel.send(content="Live training message has been deleted,"
                                                  " which means that participants tracking doesn't work now. "
                                                  f"Enter ```.training cancel {training_id}``` to avoid errors and then"
                                                  f"```.training uncancel {training_id}``` if you want to post again.")

@muddi.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if str(reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.message_ids and reaction.user_id != muddi.user.id:
        training = Training.get_for_message_ids([reaction.message_id])[0]
        if any(p.discord_id == reaction.user_id for p in training.participants):
            return
        user = User.get_for_discord_id_or_tag(reaction.user_id, "no tag")
        if not user:
            uid = User(None, name=reaction.member.display_name, discord_tag=str(reaction.member)).insert()
        else:
            uid = user.user_id
        training.add_participant(uid)
        muddi.trainings_lock.release()
        if training.cancelled or any(p.discord_id == reaction.user_id for p in training.participants):
            return
        await muddi.update_training_post(training)
    else:
        muddi.trainings_lock.release()


@muddi.event
async def on_raw_reaction_remove(reaction: discord.RawReactionActionEvent):
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if str(
            reaction.emoji) == muddi.add_emoji and reaction.message_id in muddi.message_ids and reaction.user_id != muddi.user.id:
        training = Training.get_for_message_ids([reaction.message_id])[0]
        training.remove_participant(User.get_for_discord_id_or_tag(reaction.user_id).user_id)
        if training.cancelled:
            return
        muddi.trainings_lock.release()
        await muddi.update_training_post(training)
    else:
        muddi.trainings_lock.release()


def check_channel(ctx: commands.Context):
    return ctx.channel.id == secrets.managing_channel

@muddi.command()
@commands.check(check_channel)
async def dump(ctx: commands.Context):
    """ Get the database (SQLite3) sent as DM """
    with open(secrets.database_path, 'rb') as data_dump:
        await ctx.author.send(file=discord.File(data_dump, 'dump.db'))


@muddi.group(name="training")
@commands.check(check_channel)
async def _training(ctx):
    """ Command for all things related organization of trainings."""
    if ctx.invoked_subcommand is None:
        await ctx.send("Enter `help` to learn how to use `training`")

@_training.command()
async def active(ctx):
    """ Active training posts from today to next week"""
    tr = Training.select_next_trainings(include_cancelled=True)
    embed = discord.Embed(title="Posted trainings of today and the next week")
    fmt = "%A, %d. %b %Y %H:%Mh"
    for t in tr:
        c = "[CANCELLED] " if t.cancelled else ""
        message = await muddi.posting_channel.fetch_message(t.message_id)
        embed.add_field(name=f"ID: {t.training_id} - {c}{t.start.strftime(fmt)} {t.location} with {t.coach}"
                             f" - currently {len(t.participants)} participants", value=message.jump_url, inline=False)
    await ctx.send(embed=embed)


@_training.command(name="csv")
async def training_csv(ctx: commands.Context, training_id):
    """ Receive a csv listing all participants of the given training. """
    if not muddi.trainings_lock.acquire():
        print("Couldn't acquire trainings lock")
        return

    def quotes(x):
        return f"\"{x}\""

    if training := Training.get_for_id(training_id):
        participants = deepcopy(training.participants)
        filename = f"{training.start.strftime('%Y-%m-%d-%H-%M')}-" \
                   f"{training.location}{('-' + training.coach).strip().replace(' ', '-') if training.coach else ''}" \
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
async def no_show(ctx: commands.Context, training_id, user_tag):
    """ Marks users as dirty no-show. Shame on them! """
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    try:
        # just to be safe
        user_tag = str(await commands.MemberConverter().convert(ctx, user_tag))
        if tr := Training.get_for_id(training_id):
            if usr := next((u for u in tr.participants if u.discord_tag == user_tag)):
                tr.no_show(usr.user_id)
                await ctx.send(content=f"{ctx.author.mention}")
    except commands.BadArgument as e:
        await ctx.send(content="Invalid tag!")
    except commands.CommandError:
        await ctx.send(content="Something went wrong! Try again or contact admin.")
    finally:
        muddi.trainings_lock.release()


@_training.command()
async def cancel(ctx: commands.Context, training_id: int):
    """ Cancel a training that has been posted and has not ended more than 23 hours ago."""
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if tr := Training.get_for_id(training_id):
        if tr.cancelled == 1:
            await ctx.send(content=f"{ctx.author.mention}, training #{training_id} has been cancelled already!")
            muddi.trainings_lock.release()
            return
        tr.cancelled = 1
        tr.update()
        muddi.trainings_lock.release()
        message_id = tr.message_id
        embed = cancel_embed(tr)
        discord_tags = [f"@{p.discord_tag}" for p in tr.participants if p.discord_tag]
        post = await muddi.posting_channel.fetch_message(message_id)
        await post.edit(embed=embed)
        broadcast = f" Use ```" \
                    f"{' '.join(discord_tags)}``` to notify all participants (except guests)." if discord_tags else ""
        await ctx.send(f"{ctx.author.mention}, training #{training_id} has been cancelled.{broadcast}")
    else:
        muddi.trainings_lock.release()

@_training.command()
async def uncancel(ctx: commands.Context, training_id: int):
    """ Reactivates the training instance. Posts a new message, if the old one was deleted. """
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    if tr := Training.get_for_id(training_id):
        muddi.trainings_lock.release()
        if not tr:
            await ctx.send(content=f"{ctx.author}, I couldn't find a training under this id!")
            return
        elif not tr.cancelled:
            await ctx.send(f"{ctx.author.mention} training #{training_id} wasn't cancelled!")
            return

        tr.cancelled = 0
        try:
            await muddi.posting_channel.fetch_message(tr.message_id)
            muddi.message_ids.append(tr.message_id)
            await muddi.update_training_post(tr)  # hopefully won't lead to inconsistencies :S
            tr.update()
            await ctx.send(content=f"{ctx.author.mention}, training #{training_id} has been uncancelled.")

        except discord.NotFound:
            await muddi.post_training(tr)  # new message ID is going to be added in this method
            await muddi.update_training_post(tr)
            await ctx.send(content=f"{ctx.author.mention}, I posted a new message, since the old one was deleted.")


@_training.group("set")
async def training_set(ctx):
    """ Use to change coach or description"""


async def training_set_attribute(ctx, training_id: int, attr: str, new_value):
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire lock!")
        return
    training = Training.get_for_id(training_id)
    if not training:
        await ctx.send(content=f"Training with ID {training_id} doesn't exist!")
        return
    setattr(training, attr, new_value)
    training.update()
    muddi.trainings_lock.release()
    await muddi.update_training_post(training)
    await ctx.send(content="Successfully changed training!")


@training_set.command("coach")
async def training_set_coach(ctx, training_id: int, coach: str):
    """ Change the coach field of the training. Put the whole coach string in quotation marks if it involves spaces."""
    await training_set_attribute(ctx, training_id=training_id, attr="coach", new_value=coach)


# breaking
async def training_set_location(ctx, training_id: int, location: str):
    await training_set_attribute(ctx, training_id=training_id, attr="location", new_value=location)


@training_set.command("description")
async def training_set_description(ctx, training_id: int, description: str):
    """ Put the description in quotes """
    await training_set_attribute(ctx, training_id=training_id, attr="description", new_value=description)


# breaking
async def training_set_start(ctx, training_id: int, start: str):
    """ Change the start time in HH:MM format """
    try:
        t = datetime.strptime(start, "%H:%M")
        new_time = Training.get_for_id(training_id).start.replace(hour=t.hour, minute=t.minute)
        await training_set_attribute(ctx, training_id=training_id, attr="start", new_value=new_time)
    except ValueError:
        await ctx.send(content="Wrong format! Example: 20:15")

# breaking
async def training_set_end(ctx, training_id: int, end: str):
    """ Change the end time in HH:MM format """
    try:
        t = datetime.strptime(end, "%H:%M")
        new_time = Training.get_for_id(training_id).end.replace(hour=t.hour, minute=t.minute)
        await training_set_attribute(ctx, training_id=training_id, attr="end", new_value=new_time)
    except ValueError:
        await ctx.send(content="Wrong format! Example: 20:15")

@_training.group("add")
async def training_add(ctx):
    """ Add a guest to the list. The spreadsheet id is the row number taken from
    https://docs.google.com/spreadsheets/d/1EBDeTRijlMmmbAiXnrs05RyveKYRahykTnVJ4x1RMG4/edit?usp=sharing"""
    if ctx.invoked_subcommand is None:
        await ctx.send("Use `training add guest \{training id\} \{spreadsheet id\} to add a guest")


@_training.group("remove")
async def training_remove(ctx):
    """ Remove a guest from the participants list. The name is the displayed name in the participants list."""
    if ctx.invoked_subcommand is None:
        await ctx.send("Use `training remove guest \{training id\} \"{guest name}\" to remove")


@training_add.command(name="guest")
async def add_guest(ctx, training_id: int, guest_rowid: int):
    """ Add a guest to the list. The spreadsheet id is the row number taken from
    https://docs.google.com/spreadsheets/d/1EBDeTRijlMmmbAiXnrs05RyveKYRahykTnVJ4x1RMG4/edit?usp=sharing"""
    sheet = sh.Spreadsheet()
    if not (guest_row := sheet.get_guest_at_row(row_id=guest_rowid)) or guest_row[sh.member_type] != sh.GUEST:
        await ctx.send(content="The referenced row isn't a valid guest entry!")
        return
    # while the training is being worked on, it shouldn't be altered in the database
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    tr: Training = Training.get_for_id(training_id)
    if not tr:
        await ctx.send(content=f"Training: with ID {training_id} not found!")
    else:
        # check if guest is in database
        user = User.get_guest_for_name(guest_row[sh.u_name])
        if not user:
            User.update_from_sheet()
            user = User.get_guest_for_name(guest_row[sh.u_name])
        if user.name in [p.name for p in tr.participants]:
            await ctx.send(content=f"This person is already a participant!")
            return
        success = tr.add_participant(user_id=user.user_id)
        muddi.trainings_lock.release()
        if not success:
            await ctx.send(content=f"Something went wrong when trying to add participant to training #{training_id}")
            return
        if tr.message_id not in muddi.message_ids:
            muddi.message_ids.append(tr.message_id)
        await muddi.update_training_post(tr)
        await ctx.send(content=f"{ctx.author.mention}, {user.name} has been added to training #{training_id}")


@training_remove.command(name="guest")
async def remove_guest(ctx: commands.Context, training_id: int, name: str):
    """ Remove a guest from the participants list. The name is the displayed name in the participants list."""
    if not muddi.trainings_lock.acquire(timeout=5):
        print("couldn't acquire trainings lock")
        return
    trainings = muddi.trainings().values()
    for tr in trainings:
        if tr.training_id == training_id:
            for p in tr.participants:
                if p.member_type == sh.GUEST and p.name == name:
                    if tr.remove_participant(p.user_id):
                        muddi.trainings_lock.release()
                        await muddi.update_training_post(tr)
                        await ctx.send(content=f"{ctx.author.mention}, {name} has been removed from training #{training_id}")
                        return
    muddi.trainings_lock.release()
    past_training = Training.get_for_id(training_id)
    if past_training:
        if past_training.remove_guest_participant(name):
            await muddi.update_training_post(past_training)
            await ctx.send(content=f"Successfully removed {name} from training #{training_id}")


async def remove_guest_name(training: Training, name: str):
    for p in training.participants:
        if p.name.lower() == name.lower() and p.member_type == sh.GUEST:
            training.remove_participant(p.user_id)


muddi.run(secrets.bot_token)
