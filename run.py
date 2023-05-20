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
                    user_id INTEGER PRIMARY KEY,
                    total_time INTEGER DEFAULT 0,
                    current_rank INTEGER DEFAULT 0
                )''')
conn.commit()

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')

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
            await start_timer(member)

    if before.channel is not None:
        # User left a voice channel
        if not member.bot:
            await stop_timer(member)

async def start_timer(member):
    if member.id not in bot.voice_timers:
        bot.voice_timers[member.id] = datetime.datetime.now()

async def stop_timer(member):
    if member.id in bot.voice_timers:
        start_time = bot.voice_timers.pop(member.id)
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        total_hours = duration.total_seconds() / 3600

        # Update the total time and current rank in the database
        cursor.execute("SELECT total_time, current_rank FROM voice_records WHERE user_id = ?", (member.id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("INSERT INTO voice_records (user_id, total_time, current_rank) VALUES (?, ?, ?)",
                           (member.id, duration.total_seconds(), 0))
        else:
            total_time = row[0] + duration.total_seconds()
            current_rank = row[1]
            cursor.execute("UPDATE voice_records SET total_time = ?, current_rank = ? WHERE user_id = ?",
                           (total_time, current_rank, member.id))
        conn.commit()

        # Check if the user has reached the next rank
        if 'current_rank' in locals():
            for rank in RANKS:
                if current_rank < len(RANKS) - 1 and total_hours >= rank['max_hours'] and total_hours < RANKS[current_rank + 1]['max_hours']:
                    next_rank_role = discord.utils.get(member.guild.roles, name=rank['name'])
                    await member.add_roles(next_rank_role)
                    cursor.execute("UPDATE voice_records SET current_rank = ? WHERE user_id = ?", (current_rank + 1, member.id))
                    conn.commit()
                    logger.info(f'{member.name} has been promoted to {rank["name"]}')
                    break


# Initialize the voice_timers dictionary
bot.voice_timers = {}

bot.run(TOKEN)

# Close the database connection
conn.close()
