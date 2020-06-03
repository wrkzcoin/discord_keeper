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
# redis
import redis

redis_pool = None
redis_conn = None

def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=0)


WORD_FILTER = ["libra", "http", "cheap", "buy", "fаcebook", "imgur", "website", "tweet", "twit", ".net", ".com", ".io", ".org", ".gq"]
NAME_FILTER = ["_bot", "giveaway", "glveaway", "give_away", "b0t"]

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
async def on_message(message):
    global WORD_FILTER
    botLogChan = bot.get_channel(id=config.discord.channelID)
    if any(word.lower() in message.content.lower() for word in WORD_FILTER):
        member = message.author
        account_created = member.created_at
        account_joined = member.joined_at
        if (datetime.utcnow() - account_joined).total_seconds() < 2*3600 or \
        (datetime.utcnow() - account_created).total_seconds() < 2*3600:
            # If just joined and post filtered word
            try:
                await message.delete()
                to_send = '{0.mention} (`{1.id}`) has been removed from {2.name}! Spammer / Scammer!'.format(member, member, member.guild)
                await member.send(to_send)
                await member.guild.kick(member)
                await botLogChan.send(to_send)
            except Exception as e:
                print(e)


@bot.event
async def on_member_join(member):
    global NAME_FILTER, redis_pool, redis_conn
    time_out_react = 30
    last_30s_join = 1
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    if redis_conn.exists('WrkzdBot_30s'):
        last_30s_join = int(redis_conn.get('WrkzdBot_30s'))
        last_30s_join += 1
        redis_conn.set('WrkzdBot_30s', str(last_30s_join), ex=30)
    else:
        try:
            redis_conn.set('WrkzdBot_30s', str(last_30s_join), ex=30)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    if last_30s_join >= 7:
        time_out_react = 5   
    elif last_30s_join >= 5:
        time_out_react = 10
    else:
        time_out_react = 5*60
    EMOJI_OK_BOX = "\U0001F197"
    EMOJI_OK_HAND = "\U0001F44C"
    botLogChan = bot.get_channel(id=config.discord.channelID)
    botReactChan = bot.get_channel(id=config.discord.CaptchaChanID)
    account_created = member.created_at

    if (datetime.utcnow() - account_created).total_seconds() >= 7200:
        to_send = '{0.mention} (`{1.id}`) has joined {2.name}!'.format(member, member, member.guild)
    else:
        if time_out_react >=30:  time_out_react = 30
        to_send = '{0.mention} (`{1.id}`) has joined {2.name}! **Warning!!!**, {3.mention} just created his/her account less than 2hr.'.format(member, member, member.guild, member)
    await botLogChan.send(to_send)

    # if name contain name filter.
    if any(word.lower() in member.name.lower() for word in NAME_FILTER):
        try:
            msg = await member.send("{} Your name is in filtered list in {}. We remove you from {} server. Sorry for this inconvenience.".format(member.mention, member.guild.name, member.guild.name))
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            pass
        await member.guild.kick(member)
        to_send = '{0.mention} (`{1.id}`) has been removed from {2.name}! Filtered name matched.'.format(member, member, member.guild)
        await botLogChan.send(to_send)
        return

    try:
        msg = await member.send("{} Please re-act OK in this message within {}s. Otherwise, we will consider you as bot and remove you from {} server. You can re-act also on my public mention message.".format(member.mention, time_out_react, member.guild.name))
        await msg.add_reaction(EMOJI_OK_BOX)
        msg = await botReactChan.send("{} Please re-act OK in this message within {}s. Otherwise, we will consider you as bot and remove you from {} server. You can also re-act on my DM.".format(member.mention, time_out_react, member.guild.name))
        await msg.add_reaction(EMOJI_OK_BOX)
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        pass
    
    def check(reaction, user):
        return user == member and (reaction.emoji == EMOJI_OK_BOX or reaction.emoji == EMOJI_OK_HAND)and reaction.message.author == bot.user

    try:
        reaction, user =  await bot.wait_for('reaction_add', timeout=time_out_react, check=check)
    except asyncio.TimeoutError:
        # get user, they might left or got kicked from spamming before timeout
        get_member = bot.get_user(id=member.id)
        if get_member:
            to_send = '{0.mention} (`{1.id}`) has been removed from {2.name}! No responding on OK emoji.'.format(member, member, member.guild)
            await botLogChan.send(to_send)
            try:
                await member.send("You have been removed from {} because of timeout on re-action OK. Sorry for this inconvenience.".format(member.guild.name))
            except asyncio.TimeoutError:
                pass
            await member.guild.kick(member)
    else:
        # check if user re-act
        try:
            await botReactChan.send("Thank you {0.mention} for verification.".format(member))
            await member.send("Thank you {0.mention} for verification.".format(member))
        except (discord.Forbidden, discord.errors.Forbidden) as e:
            pass


@bot.event
async def on_member_remove(member):
    botLogChan = bot.get_channel(id=config.discord.channelID)
    to_send = '{0.mention} (`{1.name}`) has left {2.name}!'.format(member, member, member.guild)
    await botLogChan.send(to_send)


@click.command()
def main():
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
