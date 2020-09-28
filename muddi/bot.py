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
    def __init__(self, command_prefix, update_interval=60, trainings=None, add_emoji="\U0001F195"):
        if trainings is None:
            trainings = {}
        self.command_prefix = command_prefix
        self.update_interval = update_interval
        self.trainings: Dict[MessageID, Training] = trainings
        self.trainings_lock = RLock()
        self.add_emoji = add_emoji
        self.guild: discord.Guild = None
        self.posting_channel: discord.TextChannel = None
        self.managing_channel: discord.TextChannel = None
        self._user_ids: Dict[DiscordUserID, User] = None
        self.user_ids_lock = RLock()
        super().__init__(command_prefix=command_prefix)

    @property
    def user_ids(self):
        if not self._user_ids:
            self._user_ids = dict(map(lambda u: (u.discord_id, u), User.get_all()))
        return self._user_ids

    def update_user_ids(self):
        self._user_ids = dict(map(lambda u: (u.discord_id, u), User.get_all()))

    @tasks.loop(minutes=2)
    async def schedule_loop(self):
        print("Running schedule loop")
        t1 = time.time()
        # update user lists
        User.sync(self.guild.members)
        self.members = User.get_all()
        # check schedules
        schedules = Schedule.get_schedules()
        for schedule in schedules:
            # add training to list if the next training for this schedule has been posted
            if training := schedule.scheduled():
                if not self.trainings_lock.acquire(timeout=5):
                    print("couldn't acquire trainings lock")
                    return
                if not training.cancelled and training.message_id and training.message_id not in self.trainings.keys():
                    self.trainings[training.message_id] = training
                elif not training.message_id:
                    print("This shouldn't happen. A training has been scheduled without message_id")
                self.trainings_lock.release()
            elif (ndate := schedule.next_notification()) <= (tdate := date.today()):
                new = schedule.next_training()
                await self.post_training(new)
        # check remaining pending trainings
        if not self.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        remaining = list(filter(lambda x: x.message_id not in self.trainings.keys(),
                                Training.select_next_trainings()))
        for tr in remaining:
            self.trainings[tr.message_id] = tr
        # trainings are unwatched 1 day after end
        self.trainings = dict(filter(lambda item: (item[1].end + timedelta(hours=23)) > datetime.today(),
                                     self.trainings.items()))
        self.trainings_lock.release()
        print(time.time() - t1)

    async def post_training(self, training: Training):
        post = await self.posting_channel.send(embed=posting_embed(training, [], self.add_emoji))
        await post.add_reaction(self.add_emoji)
        training.message_id = post.id
        training_id = training.insert()
        if not training_id:
            print("Error when inserting into SQLite.")  # TODO handle error
        training.training_id = training_id
        if not self.trainings_lock.acquire(timeout=5):
            print("couldn't acquire trainings lock")
            return
        self.trainings[training.message_id] = training
        tr = deepcopy(training)
        self.trainings_lock.release()
        await self.managing_channel.send(embed=managing_embed(tr, post))


