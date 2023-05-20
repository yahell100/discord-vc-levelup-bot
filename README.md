# VoiceChat LevelUp Discord Bot

VoiceChat LevelUp is a Python-based Discord bot that monitors and records the time users spend in voice chat channels. The bot keeps track of each user's total voice chat duration and assigns them a rank if they exceed a specified maximum time limit. It utilizes the discord.py library and stores the user records in an SQLite database.

## Features

- Monitors voice chat events, tracking user join and leave times.
- Calculates the duration of voice chat sessions and updates the total time for each user.
- Assigns a rank role to users who exceed the specified maximum time limit.
- Uses an SQLite database to store user records, allowing persistence across bot restarts.
- Configurable maximum time limit and rank role.

## Getting Started (Docker Compose)

To get started with the VoiceChat LevelUp bot using docker compose, follow these steps:

1. Clone the repository to your local machine.
3. Create a Discord bot application on the Discord Developer Portal and obtain a bot token.
4. Copy the file `.env.sample` to `.env`
5. Create a empty file called `bot.db`
4. In `.env`, set up the bot token in the script by replacing `'DISCORD_TOKEN'` with your actual bot token.
5. In `.env`, define your ranks by replacing value for `name` with the rank name and `max_hours` with defined threshold in hours.
6. Run `docker compose up -d`
## Getting Started (Python)

To get started with the VoiceChat LevelUp bot on Python, follow these steps:

1. Clone the repository to your local machine.
2. Install the necessary dependencies by running `pip install -r requirements.txt`.
3. Create a Discord bot application on the Discord Developer Portal and obtain a bot token.
4. Copy the file `.env.sample` to `.env`
4. In `.env`, set up the bot token in the script by replacing `'DISCORD_TOKEN'` with your actual bot token.
5. In `.env`, define your ranks by replacing value for `name` with the rank name and `max_hours` with defined threshold in hours.
6. Run the script using `python bot.py` to start the bot.
7. Invite the bot to your Discord server and grant it the necessary permissions.
8. The bot will now monitor and record voice chat sessions, assigning the rank role to users who exceed the maximum time limit.

Please note that this is a basic implementation, and you may need to customize it further to suit your specific requirements.

## License

This project is licensed under the [MIT License](LICENSE).

