import os
import boto3
import json

def get_discord_bot_token():
    s3 = boto3.client('s3')
    
    # The bucket name and the object key (file path) in the bucket
    bucket_name = os.environ.get('SECRETS_BUCKET')
    object_key = 'secrets.json'  # Adjust this if the file is located in a folder within the bucket
    
    # Fetch the file from S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        
        # Parse the JSON content
        secrets = json.loads(content)
        
        # Retrieve the DISCORD_BOT_TOKEN
        discord_bot_token = secrets.get('DISCORD_BOT_TOKEN')
        
        if not discord_bot_token:
            raise ValueError("DISCORD_BOT_TOKEN not found in secrets.json")
        
        return discord_bot_token
    
    except Exception as e:
        print(f"Error retrieving DISCORD_BOT_TOKEN from S3: {e}")
        raise

# Use the retrieved token to run your bot
discord_bot_token = get_discord_bot_token()

# Now run the bot with the retrieved token
import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="!")

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

bot.run(discord_bot_token)
