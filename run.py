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

# Get ranks from environment variable or fallback to default ranks
RANKS = os.getenv('RANKS', '[{"name": "Rank 1", "max_hours": 5}, {"name": "Rank 2", "max_hours": 10}, {"name": "Rank 3", "max_hours": 15}]')
RANKS = json.loads(RANKS)

# Get the database file name from environment variable or fallback to default name
DATABASE_FILE = os.getenv('DATABASE_FILE', 'bot.db')

intents = discord.Intents.default()
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

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
conn.commit()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='voice chat'))

    # Log the defined ranks
    logger.info('Defined ranks:')
    for rank in RANKS:
        logger.info(f'Name: {rank["name"]}, Max Hours: {rank["max_hours"]}')

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
        if current_rank < len(RANKS) - 1 and total_hours >= RANKS[current_rank]['max_hours'] and total_hours < RANKS[current_rank + 1]['max_hours']:
            next_rank_role = discord.utils.get(member.guild.roles, name=RANKS[current_rank + 1]['name'])
            await member.add_roles(next_rank_role)
            cursor.execute("UPDATE voice_records SET current_rank = ? WHERE user_id = ?", (current_rank + 1, member.id))
            conn.commit()
            logger.info(f'{member.name} has been promoted to {RANKS[current_rank + 1]["name"]}')

            if MSG_USER:
                await member.send(f'Congratulations, you have been promoted to {RANKS[current_rank + 1]["name"]} in {member.guild.name} server!')
                logger.info(f'Notified {member.name} about promotion')

# Initialize the voice_timers dictionary
bot.voice_timers = {}

bot.run(TOKEN)

# Close the database connection
conn.close()
