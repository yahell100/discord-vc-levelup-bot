import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option
import datetime
import asyncio
import logging
import sqlite3
import os
import sys
from dotenv import load_dotenv
import dateutil.parser

load_dotenv()

# Get the token from the environment variable or fallback to .env file or default value
TOKEN = os.getenv('DISCORD_TOKEN', '') or os.getenv('TOKEN', '')

# Opts to allow bot to send notification about promotion
MSG_USER = os.getenv('MSG_USER', 'False')

# Get the database file name from environment variable or fallback to default name
DATABASE_FILE = os.getenv('DATABASE_FILE', 'bot.db')

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
slash = SlashCommand(bot, sync_commands=True)

# Configure logger
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Create a console handler and set its formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))

# Create a file handler and set its formatter
file_handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))

# Add both handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Check if the database file exists, create it if it doesn't
if not os.path.exists(DATABASE_FILE):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.close()

# Create SQLite database connection
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()


# Create table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS voice_records (
                    user_id INTEGER,
                    server_id INTEGER,
                    start_time TEXT,
                    total_time INTEGER DEFAULT 0,
                    current_rank INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, server_id)
                )''')

# Create server_ranks table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS server_ranks (
                    server_id INTEGER,
                    rank_name TEXT,
                    max_hours INTEGER,
                    PRIMARY KEY (server_id, rank_name)
                )''')

conn.commit()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='voice chat'))

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel == after.channel:
        return  # Ignore if the user didn't change the voice channel

    if after.channel is not None:
        # User joined a voice channel
        if not member.bot:
            for guild in bot.guilds:
                if member.guild == guild:
                    check_user_exists(member.id, member.guild.id)
                    await start_timer(member)
                    break

    if before.channel is not None:
        # User left a voice channel
        if not member.bot:
            for guild in bot.guilds:
                if member.guild == guild:
                    await stop_timer(member)
                    break

def check_user_exists(user_id, server_id):
    cursor.execute("SELECT COUNT(*) FROM voice_records WHERE user_id = ? AND server_id = ?", (user_id, server_id))
    row = cursor.fetchone()
    if row[0] == 0:
        cursor.execute("INSERT INTO voice_records (user_id, server_id, start_time, total_time, current_rank) VALUES (?, ?, ?, ?, ?)",
                       (user_id, server_id, None, 0, 0))
        conn.commit()

async def start_timer(member):
    server_id = member.guild.id
    user_id = member.id
    start_time = datetime.datetime.now()
    start_time_str = start_time.isoformat()

    cursor.execute("SELECT user_id FROM voice_records WHERE user_id = ? AND server_id = ?", (user_id, server_id))
    row = cursor.fetchone()

    if row is None:
        # Insert a new record if the user is not in the database
        cursor.execute("INSERT INTO voice_records (user_id, server_id, start_time) VALUES (?, ?, ?)", 
                       (user_id, server_id, start_time_str))
        logger.debug(f'Started timer and created new record for user: {member.name} in server: {server_id} at {start_time_str}')
    else:
        # If the user already exists in the database, just update the start_time
        cursor.execute("UPDATE voice_records SET start_time = ? WHERE user_id = ? AND server_id = ?", 
                       (start_time_str, user_id, server_id))
        logger.debug(f'Started timer and updated start time for user: {member.name} in server: {server_id} to {start_time_str}')

    # Commit changes to the database
    conn.commit()
    logger.debug(f'Timer started for user: {member.name} in server: {server_id}')

async def stop_timer(member):
    server_id = member.guild.id
    user_id = member.id

    # Pull the start_time from the database
    cursor.execute("SELECT start_time, total_time, current_rank FROM voice_records WHERE user_id = ? AND server_id = ?",
                   (user_id, server_id))
    row = cursor.fetchone()
    if row is None:
        # Handle if the record doesn't exist (shouldn't occur)
        logger.warning(f'No timer found for user: {member.name} in server: {server_id}')
        return

    start_time_str = row[0]  # Get the start_time as a string
    total_time = row[1]
    current_rank = row[2]

    # Convert the start_time string back to a datetime object
    start_time = dateutil.parser.parse(start_time_str)
    logger.debug(f'Start time for user: {member.name} in server: {server_id} is {start_time}')

    # Calculate the duration and total time
    end_time = datetime.datetime.now()
    duration = end_time - start_time
    total_time += duration.total_seconds()
    logger.debug(f'Duration for user: {member.name} in server: {server_id} is {duration} seconds')

    # Update the total_time in the database
    cursor.execute("UPDATE voice_records SET total_time = ? WHERE user_id = ? AND server_id = ?",
                   (total_time, user_id, server_id))
    logger.debug(f'Updated total time for user: {member.name} in server: {server_id} to {total_time} seconds')

    # Calculate total_hours for rank threshold checks
    total_hours = total_time / 3600

    # Check if the user has reached the next rank
    cursor.execute("SELECT rank_name, max_hours FROM server_ranks WHERE server_id = ?", (server_id,))
    ranks = cursor.fetchall()

    if current_rank < len(ranks) - 1:
        current_max_hours = ranks[current_rank][1]
        next_rank_name = ranks[current_rank + 1][0]
        next_max_hours = ranks[current_rank + 1][1]

        if total_hours >= current_max_hours and total_hours < next_max_hours:
            next_rank_role = discord.utils.get(member.guild.roles, name=next_rank_name)
            await member.add_roles(next_rank_role)
            cursor.execute("UPDATE voice_records SET current_rank = ? WHERE user_id = ? AND server_id = ?",
                           (current_rank + 1, user_id, server_id))
            logger.info(f'{member.name} has been promoted to {next_rank_name} in server: {server_id}')

            if MSG_USER.lower() == 'true':
                await member.send(f'Congratulations! You have been promoted to {next_rank_name} in server: {member.guild.name}.')

    # Commit changes and close the connection
    conn.commit()
    logger.debug(f'Changes committed to database for user: {member.name} in server: {server_id}')


@slash.slash(
    name="add_rank",
    description="Adds a new rank with the specified name and maximum hours.",
    options=[
        create_option(
            name="rank_name",
            description="The name of the rank.",
            option_type=3,
            required=True
        ),
        create_option(
            name="max_hours",
            description="The maximum number of hours for the rank.",
            option_type=4,
            required=True
        )
    ],
    default_permission=False
)
@commands.has_permissions(administrator=True)
async def add_rank(ctx, rank_name: str, max_hours: int):
    server_id = ctx.guild.id

    cursor.execute("SELECT COUNT(*) FROM server_ranks WHERE server_id = ? AND rank_name = ?", (server_id, rank_name))
    row = cursor.fetchone()
    if row[0] == 0:
        cursor.execute("INSERT INTO server_ranks (server_id, rank_name, max_hours) VALUES (?, ?, ?)",
                       (server_id, rank_name, max_hours))
        conn.commit()
        logger.info(f'Rank "{rank_name}" added in server: {server_id}')
        await ctx.send(f'Rank "{rank_name}" added.')
    else:
        await ctx.send(f'Rank "{rank_name}" already exists.')


@slash.slash(
    name="remove_rank",
    description="Removes the specified rank.",
    options=[
        create_option(
            name="rank_name",
            description="The name of the rank to remove.",
            option_type=3,
            required=True
        )
    ],
    default_permission=False
)
@commands.has_permissions(administrator=True)
async def remove_rank(ctx, rank_name: str):
    server_id = ctx.guild.id

    cursor.execute("SELECT COUNT(*) FROM server_ranks WHERE server_id = ? AND rank_name = ?", (server_id, rank_name))
    row = cursor.fetchone()
    if row[0] > 0:
        cursor.execute("DELETE FROM server_ranks WHERE server_id = ? AND rank_name = ?", (server_id, rank_name))
        conn.commit()
        logger.info(f'Rank "{rank_name}" removed from server: {server_id}')
        await ctx.send(f'Rank "{rank_name}" removed.')
    else:
        await ctx.send(f'Rank "{rank_name}" not found.')


@slash.slash(
    name="list_ranks",
    description="Lists all the ranks for the server.",
    default_permission=False
)
@commands.has_permissions(administrator=True)
async def list_ranks(ctx):
    server_id = ctx.guild.id

    cursor.execute("SELECT rank_name, max_hours FROM server_ranks WHERE server_id = ?", (server_id,))
    ranks = cursor.fetchall()

    if len(ranks) > 0:
        rank_list = '\n'.join([f'{rank[0]}: {rank[1]} hours' for rank in ranks])
        await ctx.send(f'**Ranks for server {ctx.guild.name}:**\n{rank_list}')
    else:
        await ctx.send(f'No ranks found for server {ctx.guild.name}.')


@slash.slash(
    name="promote_user",
    description="Promotes the specified user to the next rank.",
    options=[
        create_option(
            name="user",
            description="The user to promote.",
            option_type=6,
            required=True
        )
    ],
    default_permission=False
)
@commands.has_permissions(administrator=True)
async def promote_user(ctx, user: discord.User):
    server_id = ctx.guild.id
    user_id = user.id

    cursor.execute("SELECT start_time, total_time, current_rank FROM voice_records WHERE user_id = ? AND server_id = ?",
                   (user_id, server_id))
    row = cursor.fetchone()

    if row is not None:
        start_time_str = row[0]  # Get the start_time as a string
        total_time = row[1]
        current_rank = row[2]

        cursor.execute("SELECT rank_name, max_hours FROM server_ranks WHERE server_id = ?", (server_id,))
        ranks = cursor.fetchall()

        if current_rank < len(ranks) - 1:
            current_max_hours = ranks[current_rank][1]
            next_rank_name = ranks[current_rank + 1][0]
            next_max_hours = ranks[current_rank + 1][1]

            if total_time >= current_max_hours and total_time < next_max_hours:
                next_rank_role = discord.utils.get(ctx.guild.roles, name=next_rank_name)
                await user.add_roles(next_rank_role)
                cursor.execute("UPDATE voice_records SET current_rank = ? WHERE user_id = ? AND server_id = ?",
                               (current_rank + 1, user_id, server_id))
                conn.commit()
                logger.info(f'{user.name} has been promoted to {next_rank_name} in server: {server_id}')
                await ctx.send(f'{user.mention} has been promoted to {next_rank_name}.')
            else:
                await ctx.send(f'{user.mention} has not reached the required hours for promotion.')
        else:
            await ctx.send(f'{user.mention} is already at the highest rank.')
    else:
        await ctx.send(f'{user.mention} is not recorded in the voice activity.')

@slash.slash(
    name="check_hours",
    description="Checks the total number of voice chat hours for a user.",
    options=[
        create_option(
            name="user",
            description="The user to check.",
            option_type=6,
            required=True
        )
    ],
    default_permission=True
)
async def check_hours(ctx, user: discord.User):
    server_id = ctx.guild.id
    user_id = user.id

    cursor.execute("SELECT total_time FROM voice_records WHERE user_id = ? AND server_id = ?", 
                   (user_id, server_id))
    row = cursor.fetchone()

    if row is not None:
        total_time = row[0]
        total_hours = total_time / 3600  # convert seconds to hours
        await ctx.send(f'{user.mention} has spent {total_hours:.2f} hours in voice chats.')
    else:
        await ctx.send(f'No record found for {user.mention}.')

@slash.slash(
    name="modify_hours",
    description="Manually modify the hours for a user.",
    options=[
        create_option(
            name="user",
            description="The user to modify.",
            option_type=6,
            required=True
        ),
        create_option(
            name="hours",
            description="The new hours value.",
            option_type=4,
            required=True
        )
    ],
    default_permission=False
)
@commands.has_permissions(administrator=True)
async def modify_hours(ctx, user: discord.User, hours: int):
    server_id = ctx.guild.id
    user_id = user.id

    cursor.execute("UPDATE voice_records SET total_time = ? WHERE user_id = ? AND server_id = ?",
                   (hours * 3600, user_id, server_id))
    conn.commit()
    logger.info(f'Hours modified for user: {user.name} in server: {server_id}')

    await ctx.send(f'Hours modified for {user.mention}.')

@slash.slash(
    name="invite",
    description="Generates an invite link for the bot.",
    default_permission=False
)
async def invite(ctx):
    permissions = discord.Permissions(
        manage_roles=True,
        read_messages=True,
        send_messages=True
    )
    invite_link = discord.utils.oauth_url(ctx.bot.user.id, permissions=permissions)
    await ctx.author.send(f"Invite link for the bot: {invite_link}")
    await ctx.send("I've sent you a direct message with the invite link!")

bot.run(TOKEN)
