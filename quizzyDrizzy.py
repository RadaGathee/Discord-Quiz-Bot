import discord
from discord.ext import commands
import asyncio
import json

import asyncpg
import random
import json
import psycopg2
import datetime
import re
from datetime import datetime, timedelta
from collections import defaultdict
import io
from discord.ext.commands import CommandNotFound



intents = discord.Intents.default()
intents.typing = False 
intents.message_content = True 


intents.presences = True



# Initialize the bot with intents
bot = commands.Bot(command_prefix="#", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.command()
async def get_messages(ctx, channel_name):
    # Find the channel by name
    channel = discord.utils.get(ctx.guild.channels, name=channel_name)
    
    if channel:
        # Fetch the last 10 messages
        messages = await channel.history(limit=10).flatten()
        
        for message in messages:
            print(f'{message.author.display_name}: {message.content}')
    else:
        await ctx.send(f'Channel {channel_name} not found.')



@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, CommandNotFound):
        await ctx.send("Command not found. Please use a valid command. Type `!help` for a list of available commands.")
    else:
        # Handle other errors gracefully, if needed
        await ctx.send(f"An error occurred: {error}")




# Load trivia questions from questions.json
with open('questions.json', 'r') as file:
    questions = json.load(file)

# PostgreSQL connection parameters
db_params = {
    'database': '',
    'user': 'postgres',
    'password': '',
    'host': 'localhost', 
}




@bot.command()
async def trivia(ctx):
    # Get a random trivia question
    question = random.choice(questions)
    
    await ctx.send(question['question'])
    
    def check(message):
        return message.author == ctx.author

    try:
        answer = await bot.wait_for('message', check=check, timeout=15.0)
    except asyncio.TimeoutError:
        await ctx.send("Time's up! The correct answer was: " + question['answer'])
    else:
        if answer.content.lower() == question['answer'].lower():
            await ctx.send(f"Correct, {ctx.author.mention}!")
            update_leaderboard(ctx.author.id, 1)
        else:
            await ctx.send(f"Sorry, {ctx.author.mention}. The correct answer was: {question['answer']}")

def update_leaderboard(user_id, score):
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO leaderboard (user_id, score) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET score = leaderboard.score + %s', (user_id, score, score))
        
        conn.commit()
    except psycopg2.Error as e:
        # Handle database connection or query errors
        print(f"An error occurred while updating the leaderboard: {str(e)}")
    finally:
        if conn is not None:
            conn.close()

@bot.command()
async def leaderboard(ctx):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM leaderboard ORDER BY score DESC')
        rows = cursor.fetchall()
        
        if not rows:
            await ctx.send("The leaderboard is empty.")
            return
        
        leaderboard_msg = 'Leaderboard:\n'
        for i, row in enumerate(rows, 1):
            user = await bot.fetch_user(int(row[0]))
            if user is not None:
                # Use display_name to get the username
                leaderboard_msg += f'{i}. {user.display_name}: {row[1]} points\n'
            else:
                # Handle the case where the user couldn't be found
                leaderboard_msg += f'{i}. User (ID: {row[0]}): {row[1]} points\n'
        
        await ctx.send(leaderboard_msg)
    except psycopg2.Error as e:
        # Handle database connection or query errors
        print(f"An error occurred while fetching the leaderboard: {str(e)}")
        await ctx.send("An error occurred while fetching the leaderboard. Please try again later.")
    finally:
        if conn is not None:
            conn.close()




@bot.command()
async def pin(ctx):
    # Check if the user has permission to pin messages in the channel
    if ctx.channel.permissions_for(ctx.author).manage_messages:
        try:
            # Get the message that the user replied to
            replied_message = ctx.message.reference.resolved if ctx.message.reference else None

            if replied_message:
                # Pin the replied message
                await replied_message.pin()
                await ctx.send(f"Message with ID {replied_message.id} has been pinned.")
            else:
                await ctx.send("You need to reply to a message that you want to pin.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to pin messages in this channel.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")


# Command to unpin a message
@bot.command()
async def unpin(ctx):
    # Check if the user has permission to manage messages in the channel
    if ctx.channel.permissions_for(ctx.author).manage_messages:
        try:
            # Get the message that the user replied to
            replied_message = ctx.message.reference.resolved if ctx.message.reference else None

            if replied_message and replied_message.pinned:
                # Unpin the replied message
                await replied_message.unpin()
                await ctx.send(f"Message with ID {replied_message.id} has been unpinned.")
            elif replied_message and not replied_message.pinned:
                await ctx.send("The replied message is not pinned.")
            else:
                await ctx.send("You need to reply to a pinned message that you want to unpin.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to unpin messages in this channel.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")



# Command to kick a user
@bot.command()
async def kick(ctx, *, reason: str = None):
    # Check if the user has permission to kick members
    if ctx.channel.permissions_for(ctx.author).kick_members:
        try:
            # Get the message that the user replied to
            replied_message = ctx.message.reference.resolved if ctx.message.reference else None

            if replied_message and replied_message.author and replied_message.author != ctx.guild.me:
                user_to_kick = replied_message.author

                # Check if the user is an administrator
                if ctx.guild.owner != user_to_kick and user_to_kick.guild_permissions.administrator:
                    await ctx.send("You cannot kick an administrator.")
                else:
                    # Kick the user with an optional reason
                    await ctx.guild.kick(user_to_kick, reason=reason)

                    # Get the username of the kicked user
                    kicked_username = user_to_kick.name

                    if reason:
                        await ctx.send(f"{kicked_username} has been kicked for the following reason: {reason}")
                    else:
                        await ctx.send(f"{kicked_username} has been kicked.")
            else:
                await ctx.send("You need to reply to a message from the user you want to kick.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to kick members in this server.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")





# Command to ban a user
@bot.command()
async def ban(ctx, *, reason: str = None):
    # Check if the user has permission to ban members
    if ctx.channel.permissions_for(ctx.author).ban_members:
        try:
            # Get the message that the user replied to
            replied_message = ctx.message.reference.resolved if ctx.message.reference else None

            if replied_message and replied_message.author and replied_message.author != ctx.guild.me:
                user_to_ban = replied_message.author

                # Check if the user is an administrator
                if ctx.guild.owner != user_to_ban and user_to_ban.guild_permissions.administrator:
                    await ctx.send("You cannot ban an administrator.")
                else:
                    # Ban the user with an optional reason
                    await ctx.guild.ban(user_to_ban, reason=reason)

                    # Get the username of the banned user
                    banned_username = user_to_ban.name

                    if reason:
                        await ctx.send(f"{banned_username} has been banned for the following reason: {reason}")
                    else:
                        await ctx.send(f"{banned_username} has been banned.")
            else:
                await ctx.send("You need to reply to a message from the user you want to ban.")
        except discord.Forbidden:
            await ctx.send("I do not have permission to ban members in this server.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred: {e}")
    else:
        await ctx.send("You do not have permission to use this command.")




with open('token.txt', 'r') as file:
    api_token = file.read().strip()

# Start the bot
bot.run(api_token)
