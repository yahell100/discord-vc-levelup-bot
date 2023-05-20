# Use the official Python image as the base image
FROM python:3.9-slim-buster

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install the required dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot script and SQLite database file to the working directory
COPY run.py .
COPY bot.db .

# Run the bot script
CMD ["python", "run.py"]
