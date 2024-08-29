import discord
import os

# Create an instance of a Client. This is the main entry point for your bot.
intents = discord.Intents.default()
intents.message_content = True  # Enable privileged intents if needed
client = discord.Client(intents=intents)

# Event that is triggered when the bot has connected to Discord
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

# Event that is triggered when a message is sent in a channel the bot has access to
@client.event
async def on_message(message):
    # Make sure the bot doesn't reply to itself
    if message.author == client.user:
        return

    # Simple command that responds to the keyword 'hello'
    if message.content.startswith('hello'):
        await message.channel.send('Hello! How can I assist you today?')

# Run the bot with the specified token
# TODO add discord token here
client.run("your-token-here")
