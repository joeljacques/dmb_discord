from functools import reduce

import discord


def managing_embed(training, message: discord.Message):
    form = "%A, %d. %b %Y %H:%Mh"
    embed = discord.Embed(title=f"{training.start.strftime(form)} {training.location}",
                          description=training.description,
                          url=message.jump_url)
    embed.add_field(name="ID", value=training.training_id)
    return embed


def cancel_embed(training):
    form = "%A, %d. %b %Y %H:%Mh"
    embed = discord.Embed(title=f"{training.start.strftime(form)} {training.location}",
                          description=training.description)
    embed.add_field(name="Coach", value=training.coach)
    embed.add_field(name="CANCELLED", value=":(")
    return embed


def embed_table(users: [(str, str)]):
    return "\n".join([f"{num + 1}. {name}: {tag or '(Guest)'}"
                      for num, (name, tag) in enumerate(users)]) or "Be the first!"  # Make pretty table


def posting_embed(training, users: [(str, str, str)], add_emoji):
    form = "%A, %d. %b %Y %H:%Mh"
    embed = discord.Embed(title=f"{training.start.strftime(form)} {training.location}",
                          description=training.description)
    embed.add_field(name="Registration", value=f"Click {add_emoji} to register. "
                                               f"Please contact {training.coach} or other coaches and techies, "
                                               f"if you want to bring guests!", inline=False)
    embed.add_field(name="Coach", value=training.coach)
    women = reduce(lambda num, el: num + 1 if el[2] == 'w' else num, users, 0)
    men = reduce(lambda num, el: num + 1 if el[2] == 'm' else num, users, 0)
    embed.add_field(name="Women", value=str(women))
    embed.add_field(name="Men", value=str(men))
    embed.add_field(name="total", value=str(len(users)))
    embed.add_field(name="Participants", value=embed_table([(n, d) for n, d, g in users]), inline=False)
    return embed
