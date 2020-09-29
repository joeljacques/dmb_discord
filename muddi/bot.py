from datetime import date, timedelta, datetime
import time
from typing import Dict
from threading import RLock
from copy import deepcopy
import discord
from discord.ext import commands, tasks

from muddi.models import Training, Schedule, User
from muddi.utils.embeds import managing_embed, posting_embed

MessageID = int
DiscordUserID = int

class Muddi(commands.Bot):
    def __init__(self, command_prefix, add_emoji="\U0001F94F", ):
        self.command_prefix = command_prefix
        self.message_ids = []
        self.trainings_lock = RLock()
        self.add_emoji = add_emoji
        self.guild: discord.Guild = None
        self.posting_channel: discord.TextChannel = None
        self.managing_channel: discord.TextChannel = None
        self.loop_count = 0
        super().__init__(command_prefix=command_prefix, help_command=commands.DefaultHelpCommand(dm_help=True))

    def trainings(self):
        trainings_list = Training.get_for_message_ids(self.message_ids)
        return {tr.message_id: tr for tr in trainings_list}

    @tasks.loop(seconds=30)
    async def schedule_loop(self):
        print("Running schedule loop")
        t1 = time.time()
        # should be fine to sync up every one in a while, since we sync when guests are added or users join the server
        if self.loop_count % 5 < 1:
            User.sync(self.guild.members)
        self.loop_count += 1
        self.members = User.get_all()
        # check schedules
        schedules = Schedule.get_schedules()
        for schedule in schedules:
            # add training to list if the next training for this schedule has been posted
            if training := schedule.scheduled():
                if not training.cancelled and training.message_id and training.message_id not in self.message_ids:
                    self.message_ids.append(training.message_id)
                elif not training.message_id:
                    print("This shouldn't happen. A training has been scheduled without message_id")
            elif schedule.next_notification() <= date.today():
                new = schedule.next_training()
                await self.post_training(new)
        # check remaining pending trainings
        if not self.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        remaining = list(filter(lambda x: x.message_id not in self.message_ids,
                                Training.select_next_trainings()))
        for tr in remaining:
            if tr.message_id not in self.message_ids:
                self.message_ids.append(tr.message_id)
        # trainings are unwatched 1 day after end
        trainings = self.trainings()
        self.message_ids = list(map(lambda x: x.message_id,
                               filter(lambda item: (item.end + timedelta(hours=23) > datetime.today()),
                                      trainings.values())))
        self.trainings_lock.release()
        print(time.time() - t1)

    async def post_training(self, training: Training):
        post = await self.posting_channel.send(embed=posting_embed(training, [], self.add_emoji))
        await post.add_reaction(self.add_emoji)
        training.message_id = post.id
        training_id = training.insert() if not training.training_id else training.training_id
        training.training_id = training_id
        self.message_ids.append(training.message_id)
        await self.managing_channel.send(content= "new training was just postet", embed=managing_embed(training, post))


