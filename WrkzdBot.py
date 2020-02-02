import discord
from discord.ext import commands
from discord.ext.commands import Bot, AutoShardedBot, when_mentioned_or, CheckFailure
from discord.utils import get

import time, timeago
from datetime import datetime
from config import config
import click
import sys, traceback
import asyncio

bot = AutoShardedBot(command_prefix=['.', '!', '?'], case_insensitive=True)
bot.remove_command("help")

@bot.event
async def on_shard_ready(shard_id):
    print(f'Shard {shard_id} connected')

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    game = discord.Game(name="Watching Human!!!")
    await bot.change_presence(status=discord.Status.online, activity=game)

@bot.event
async def on_member_join(member):
    EMOJI_OK_BOX = "\U0001F197"
    botLogChan = bot.get_channel(id=config.discord.channelID)
    botReactChan = bot.get_channel(id=config.discord.CaptchaChanID)
    account_created = member.created_at
    if (datetime.utcnow() - account_created).total_seconds() >= 7200:
        to_send = '{0.mention} (`{}`) has joined {1.name}!'.format(member, member.id, member.guild)
    else:
        to_send = '{0.mention} (`{1.id}`) has joined {2.name}! **Warning!!!**, {3.mention} just created his/her account less than 2hr.'.format(member, member.guild, member, member)
    await botLogChan.send(to_send)
    try:
        msg = await member.send("{0.mention} Please re-act OK in this message within 60s. Otherwise, we will consider you as bot and remove you from WrkzCoin server. You can re-act also on my public mention message.".format(member))
        await msg.add_reaction(EMOJI_OK_BOX)
        msg = await botReactChan.send("{0.mention} Please re-act OK in this message within 60s. Otherwise, we will consider you as bot and remove you from WrkzCoin server. You can also re-act on my DM.".format(member))
        await msg.add_reaction(EMOJI_OK_BOX)
    except (discord.Forbidden, discord.errors.Forbidden) as e:   
        pass
    
    def check(reaction, user):
        return user == member and reaction.emoji == EMOJI_OK_BOX and reaction.message.author == bot.user

    try:
        reaction, user =  await bot.wait_for('reaction_add', timeout=60, check=check)
    except asyncio.TimeoutError:
        to_send = '{0.mention} (`{1.id}`) has been removed from {2.name}! No responding on OK emoji.'.format(member, member, member.guild)
        await botLogChan.send(to_send)
        await member.guild.kick(member)
    else:
        # check if user re-act
        await botReactChan.send("Thank you {0.mention} for verification.".format(member))

@bot.event
async def on_member_remove(member):
    botLogChan = bot.get_channel(id=config.discord.channelID)
    to_send = '{0.mention} has left {1.name}!'.format(member, member.guild)
    await botLogChan.send(to_send)


@click.command()
def main():
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
