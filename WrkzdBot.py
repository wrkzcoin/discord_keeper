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

import random
import string

redis_pool = None
redis_conn = None

def randomString(stringLength=8):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))


def init():
    global redis_pool
    print("PID %d: initializing redis pool..." % os.getpid())
    redis_pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=0)


WORD_FILTER = ["libra", "http", "cheap", "fаcebook", "imgur", "website", "tweet", "twit", ".net", ".com", ".io", ".org", ".gq"]
NAME_FILTER = ["_bot", "giveaway", "glveaway", "give_away", "b0t"]

intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = AutoShardedBot(command_prefix=['.', '!', '?'], case_insensitive=True, owner_id = config.discord.ownerID, intents=intents)
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
async def on_member_update(before, after):
    botLogChan = bot.get_channel(id=config.discord.channelID)
    if before.nick != after.nick:
        await botLogChan.send(f'{before.id}: {before.nick} changes **nick** to **{after.nick}**')


@bot.event
async def on_user_update(before, after):
    botLogChan = bot.get_channel(id=config.discord.channelID)
    if before.username != after.username:
        await botLogChan.send(f'{before.id}: {before.username} changes **username** to **{after.username}**')


@bot.event
async def on_message(message):
    global WORD_FILTER
    botLogChan = bot.get_channel(id=config.discord.channelID)
    # should ignore webhook message
    if isinstance(message.channel, discord.DMChannel) == False and message.webhook_id:
        return

    if any(word.lower() in message.content.lower() for word in WORD_FILTER):
        try:
            member = message.author
            account_created = member.created_at
            account_joined = member.joined_at
            if (datetime.utcnow() - account_joined).total_seconds() < 2*3600 or \
            (datetime.utcnow() - account_created).total_seconds() < 2*3600:
                # If just joined and post filtered word
                try:
                    await message.delete()
                    await message.channel.send(f'{message.author.name}#{message.author.discriminator}\'s message contained filtered word(s) while he/she is still new here. {message.author.mention}, please wait for ~ 2 hours until you re mature here.')
                    # not to kick, just delete message
                    # await member.guild.kick(member)
                    await botLogChan.send(f'Deleted {message.author.name}#{message.author.discriminator}\'s message in `#{message.channel.name}`.')
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    # Do not remove this, otherwise, command not working.
    ctx = await bot.get_context(message)
    await bot.invoke(ctx)


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
    except (discord.Forbidden, discord.errors.Forbidden) as e:
        pass
    msg = await botReactChan.send("{} Please re-act OK in this message within {}s. Otherwise, we will consider you as bot and remove you from {} server. You can also re-act on my DM.".format(member.mention, time_out_react, member.guild.name))
    await msg.add_reaction(EMOJI_OK_BOX)

    def check(reaction, user):
        return user == member and (reaction.emoji == EMOJI_OK_BOX or reaction.emoji == EMOJI_OK_HAND)and reaction.message.author == bot.user

    try:
        reaction, user =  await bot.wait_for('reaction_add', timeout=time_out_react, check=check)
    except asyncio.TimeoutError:
        # get user, they might left or got kicked from spamming before timeout
        get_member = bot.get_user(id=member.id)
        if get_member in member.guild.members and get_member.bot == False:
            to_send = '{0.mention} (`{1.id}`) has been removed from {2.name}! No responding on OK emoji.'.format(member, member, member.guild)
            await botLogChan.send(to_send)
            try:
                await member.send("You have been removed from {} because of timeout on re-action OK. Sorry for this inconvenience.".format(member.guild.name))
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
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


async def posting_tips():
    global redis_pool, redis_conn
    await bot.wait_until_ready()
    NewsChan = bot.get_channel(id=config.randomMsg.channelNews)
    while not bot.is_closed():
        if redis_conn is None:
            try:
                redis_conn = redis.Redis(connection_pool=redis_pool)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
        while NewsChan is None:
            NewsChan = bot.get_channel(id=config.randomMsg.channelNews)
            await asyncio.sleep(1000)
        keys = redis_conn.keys("WrkzdBotMsg:*")
        if len(keys) > 0:
            response_txt = ''
            key = random.choice(keys)
            response_txt += "{}".format(redis_conn.get(key.decode('utf-8')).decode('utf-8'))
            await NewsChan.send(response_txt)
        print("Waiting for another {}".format(config.randomMsg.duration_each))
        await asyncio.sleep(config.randomMsg.duration_each)
        print("Completed waiting...")      


@bot.command(pass_context=True, name='randmsg',  aliases=['random_message'])
async def randmsg(ctx, cmd: str, *, message: str=None):
    global redis_pool, redis_conn
    if ctx.message.author.id != config.discord.ownerID:
        return
    if redis_conn is None:
        try:
            redis_conn = redis.Redis(connection_pool=redis_pool)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    cmd = cmd.upper()
    if cmd not in ["ADD", "DEL", "LIST", "LS"]:
        await ctx.send(f'{ctx.author.mention} Invalid cmd given. Available cmd **ADD | DEL | LIST**.')
        return

    if cmd == "ADD" and len(message) < 10:
        await ctx.send(f'{ctx.author.mention} Message is too short.')
        return

    if cmd == "ADD":
        rndStr = randomString(8).upper()
        key = "WrkzdBotMsg:" + rndStr
        redis_conn.set(key, message)
        await ctx.send(f'{ctx.author.mention} Sucessfully added **{rndStr}** for message: {message}.')
        return
    elif cmd == "DEL":
        key = "WrkzdBotMsg:" + message.upper()
        if redis_conn and redis_conn.exists(key):
            redis_conn.delete(key)
            await ctx.send(f'{ctx.author.mention} **{message.upper()}** message is deleted.')
            return
        else:
            await ctx.send(f'{ctx.author.mention} **{message.upper()}** doesn\'t exist.')
            return
    elif cmd == "LS" or cmd == "LIST":
        keys = redis_conn.keys("WrkzdBotMsg:*")
        # print(msgs) # [b'WrkzdBotMsg:CLBACSCZ']
        if len(keys) > 10:
            response_txt = ''
            i = 0
            for each in keys:
                response_txt += "**{}**: {}\n".format(each.decode('utf-8').replace('WrkzdBotMsg:', ''), redis_conn.get(each.decode('utf-8')).decode('utf-8'))
                i += 1
                j = 1
                if i % 10 == 0:
                    await ctx.send(f'{ctx.author.mention} List messages **[{j}]**:\n{response_txt}')
                    response_txt = ''
                    j += 1
            if len(response_txt) > 0:
                await ctx.send(f'{ctx.author.mention} List messages **[Last]**:\n{response_txt}')
            return
        elif len(keys) > 0:
            response_txt = ''
            for each in keys:
                response_txt += "**{}**: {}\n".format(each.decode('utf-8').replace('WrkzdBotMsg:', ''), redis_conn.get(each.decode('utf-8')).decode('utf-8'))
            await ctx.send(f'{ctx.author.mention} List messages:\n{response_txt}')
            return
        else:
            await ctx.send(f'{ctx.author.mention} There is no message added yet.')
            return


@click.command()
def main():
    bot.loop.create_task(posting_tips())
    bot.run(config.discord.token, reconnect=True)


if __name__ == '__main__':
    main()
