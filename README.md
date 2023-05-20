# VoiceChat LevelUp Discord Bot

VoiceChat LevelUp is a Python-based Discord bot that monitors and records the time users spend in voice chat channels. The bot keeps track of each user's total voice chat duration and assigns them a rank if they exceed a specified maximum time limit. It utilizes the discord.py library and stores the user records in an SQLite database.

## Features

- Monitors voice chat events, tracking user join and leave times.
- Calculates the duration of voice chat sessions and updates the total time for each user.
- Assigns a rank role to users who exceed the specified maximum time limit.
- Uses an SQLite database to store user records, allowing persistence across bot restarts.
- Configurable maximum time limit and rank role.

## Getting Started

To get started with the VoiceChatMonitor bot, follow these steps:

1. Clone the repository to your local machine.
2. Install the necessary dependencies by running `pip install -r requirements.txt`.
3. Create a Discord bot application on the Discord Developer Portal and obtain a bot token.
4. Set up the bot token in the script by replacing `'your_bot_token'` with your actual bot token.
5. Specify the maximum time limit by modifying the `MAX_HOURS` variable in the script.
6. Set the name of the rank role that will be assigned to users in the `set_rank_role` command.
7. Run the script using `python bot.py` to start the bot.
8. Invite the bot to your Discord server and grant it the necessary permissions.
9. The bot will now monitor and record voice chat sessions, assigning the rank role to users who exceed the maximum time limit.

Please note that this is a basic implementation, and you may need to customize it further to suit your specific requirements.

## License

This project is licensed under the [MIT License](LICENSE).
