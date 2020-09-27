from datetime import date
from functools import reduce
from typing import Dict

import discord
from discord.ext import commands, tasks

from muddi.models import Training, Schedule, User


class Muddi(commands.Bot):
    def __init__(self, command_prefix, update_interval=60, trainings=None, add_emoji="\U0001F195"):
        if trainings is None:
            trainings = {}
        self.command_prefix = command_prefix
        self.update_interval = update_interval
        self.trainings: {int: Training} = trainings
        self.add_emoji = add_emoji
        self.guild = None
        self.posting_channel: discord.TextChannel = None
        self.managing_channel = None
        self._user_ids: Dict[int, User] = None
        super().__init__(command_prefix=command_prefix)
        self.schedule_loop.start()

    @property
    def user_ids(self):
        if not self._user_ids:
            self._user_ids = dict(map(lambda u: (u.discord_id, u), User.get_all()))
        return self._user_ids

    @tasks.loop(seconds=10)
    async def schedule_loop(self):
        print("Running schedule loop")
        if not self.guild:
            print("Hä")
            return
        # update user lists
        User.sync(self.guild.members)
        self.members = User.get_all()
        # check schedules
        schedules = Schedule.get_schedules()
        for schedule in schedules:
            # add training to list if the next training for this schedule has been posted
            if training := schedule.scheduled():
                if training.message_id and training.message_id not in self.trainings.keys():
                    self.trainings[training.message_id] = training
                elif not training.message_id:
                    print("This shouldn't happen. A training has been scheduled without message_id")
            elif (ndate := schedule.next_notification()) <= (tdate := date.today()):
                new = schedule.next_training()
                await self.post_training(new)
        # check remaining pending trainings
        remaining = list(filter(lambda x: x.message_id not in self.trainings.keys(),
                                Training.select_next_trainings()))
        for tr in remaining:
            self.trainings[tr.message_id] = tr

    async def post_training(self, training: Training):
        post = await self.posting_channel.send(embed=self.posting_embed(training, []))
        await post.add_reaction(self.add_emoji)
        training.message_id = post.id
        training_id = training.insert()
        if not training_id:
            print("Error when inserting into SQLite.")  # TODO handle error
        training.training_id = training_id
        self.trainings[training.message_id] = training

    def posting_embed(self, training, users: [(str, str, str)]):
        embed = discord.Embed(title="new training date", description=training.description)
        embed.add_field(name="Registration", value=f"Click {self.add_emoji} to register. "
                             f"Please contact {training.coach} or other coaches and techies, "
                             f"if you want to bring guests!", inline=False)
        embed.add_field(name="Coach", value=training.coach)
        women = reduce(lambda num, el: num +1 if el[2] == 'w' else num, users, 0)
        men = reduce(lambda num, el: num +1 if el[2] == 'm' else num, users, 0)
        embed.add_field(name="Women", value=str(women))
        embed.add_field(name="Men", value=str(men))
        embed.add_field(name="total", value=str(len(users)))
        embed.add_field(name="Participants", value=self.embed_table([(n, d) for n, d, g in users]), inline=False)
        return embed

    def embed_table(self, users: [(str, str)]):
        return "\n".join([f"{name}: {tag}" for name, tag in users]) or "." #  Make pretty table


