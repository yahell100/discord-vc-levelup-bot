import discord
from discord.ext import commands
import datetime
import asyncio
import logging
import sqlite3
import os
import sys
from dotenv import load_dotenv
import json

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

# Configure logger
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)

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
    prefix = bot.command_prefix
    logger.info(f"The command prefix is set to: {prefix}")

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
    start_time = datetime.datetime.now().isoformat()
    
    # Check if a record already exists for the user and server
    cursor.execute("SELECT start_time FROM voice_records WHERE user_id = ? AND server_id = ?",
                   (user_id, server_id))
    existing_start_time = cursor.fetchone()
    
    if existing_start_time is None:
        # No existing record, insert a new record
        cursor.execute("INSERT INTO voice_records (user_id, server_id, start_time, total_time, current_rank) VALUES (?, ?, ?, ?, ?)",
                       (user_id, server_id, start_time, 0, 0))
    else:
        # Existing record, update the start_time
        cursor.execute("UPDATE voice_records SET start_time = ? WHERE user_id = ? AND server_id = ?",
                       (start_time, user_id, server_id))
    
    conn.commit()
    logger.debug(f'Timer started for user: {member.name} in server: {server_id}')

async def stop_timer(member):
    server_id = member.guild.id
    user_id = member.id
    if server_id in bot.voice_timers and user_id in bot.voice_timers[server_id]:
        start_time = bot.voice_timers[server_id].pop(user_id)
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        total_hours = duration.total_seconds() / 3600

        # Update the total time and current rank in the database
        cursor.execute("SELECT start_time, total_time, current_rank FROM voice_records WHERE user_id = ? AND server_id = ?",
                       (user_id, server_id))
        row = cursor.fetchone()
        if row is None:
            # Handle if the record doesn't exist (shouldn't occur)
            return

        start_time_str = row[0]  # Get the start_time as a string
        total_time = row[1] + duration.total_seconds()
        current_rank = row[2]
        cursor.execute("UPDATE voice_records SET total_time = ?, current_rank = ? WHERE user_id = ? AND server_id = ?",
                       (total_time, current_rank, user_id, server_id))
        conn.commit()
        logger.debug(f'Timer stopped for user: {member.name} in server: {server_id}, Duration: {duration}')

        # Convert the start_time string back to a datetime object
        start_time = datetime.datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%f")
        
        # Calculate the duration using the converted start_time
        duration = end_time - start_time
        total_hours = duration.total_seconds() / 3600

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
                conn.commit()
                logger.info(f'{member.name} has been promoted to {next_rank_name} in server: {server_id}')

                if MSG_USER.lower() == 'true':
                    await member.send(f'Congratulations! You have been promoted to {next_rank_name} in server: {member.guild.name}.')

    else:
        logger.warning(f'No timer found for user: {member.name} in server: {server_id}')


@bot.command()
@commands.has_permissions(administrator=True)
async def add_rank(ctx, rank_name, max_hours):
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


@bot.command()
@commands.has_permissions(administrator=True)
async def remove_rank(ctx, rank_name):
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


@bot.command()
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


@bot.command()
@commands.has_permissions(administrator=True)
async def set_hours(ctx, member: discord.Member, hours):
    server_id = ctx.guild.id
    user_id = member.id

    cursor.execute("SELECT COUNT(*) FROM voice_records WHERE user_id = ? AND server_id = ?", (user_id, server_id))
    row = cursor.fetchone()
    if row[0] > 0:
        cursor.execute("UPDATE voice_records SET total_time = ? WHERE user_id = ? AND server_id = ?",
                       (float(hours) * 3600, user_id, server_id))
        conn.commit()
        logger.info(f'Total hours set to {hours} for user: {member.name} in server: {server_id}')
        await ctx.send(f'Total hours set to {hours} for user: {member.mention}.')
    else:
        await ctx.send(f'No record found for user: {member.mention} in server: {ctx.guild.name}.')


bot.run(TOKEN)
