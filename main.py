from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import os
import json
import asyncio
from datetime import timedelta

app = Flask('')

@app.route('/')
def home():
    return "Bot is online"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

OWNER_ID = 1219951796982648913
DATA_FILE = "data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "admins": [],
            "warnings": {},
            "autorole": None,
            "welcome_channel": None,
            "log_channel": None,
            "afk_users": {},
            "anti_link": True,
            "anti_spam": True
        }, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()

admins = set(data["admins"])
warnings = data["warnings"]
autorole = data["autorole"]
welcome_channel = data["welcome_channel"]
log_channel = data["log_channel"]
afk_users = data["afk_users"]
anti_link = data["anti_link"]
anti_spam = data["anti_spam"]

sniped_message = None
spam_tracker = {}
bad_words = ["ngu", "cl", "cc"]

@bot.event
async def on_ready():
    print(f"{bot.user} is online")

def is_admin(user):
    return user.id == OWNER_ID or user.id in admins

async def send_log(guild, text):
    global log_channel
    if not log_channel:
        return
    channel = guild.get_channel(log_channel)
    if channel:
        await channel.send(text)

@bot.event
async def on_member_join(member):
    global autorole, welcome_channel
    if autorole:
        role = member.guild.get_role(autorole)
        if role:
            try:
                await member.add_roles(role)
            except Exception as e:
                print(f"Autorole Error: {e}")

    if welcome_channel:
        channel = member.guild.get_channel(welcome_channel)
        if channel:
            await channel.send(f"Welcome {member.mention} to the server!")

@bot.event
async def on_message(message):
    global spam_tracker
    if message.author.bot:
        return

    if str(message.author.id) in afk_users:
        del afk_users[str(message.author.id)]
        data["afk_users"] = afk_users
        save_data(data)
        await message.channel.send(f"{message.author.mention} is no longer AFK.")

    for user in message.mentions:
        if str(user.id) in afk_users:
            await message.channel.send(f"{user.name} is currently AFK: {afk_users[str(user.id)]}")

    content = message.content.lower()

    if anti_link:
        blocked_links = ["http://", "https://", "discord.gg", "discord.com/invite"]
        for link in blocked_links:
            if link in content:
                if not is_admin(message.author):
                    try:
                        await message.delete()
                        await message.channel.send(f"{message.author.mention}, links are not allowed here!")
                    except:
                        pass
                    return

    for word in bad_words:
        if word in content:
            if not is_admin(message.author):
                try:
                    await message.delete()
                except:
                    pass
                return

    if anti_spam:
        user_id = message.author.id
        if user_id not in spam_tracker:
            spam_tracker[user_id] = []

        spam_tracker[user_id].append(asyncio.get_event_loop().time())
        spam_tracker[user_id] = [
            t for t in spam_tracker[user_id]
            if asyncio.get_event_loop().time() - t < 5
        ]

        if len(spam_tracker[user_id]) > 5:
            if not is_admin(message.author):
                try:
                    if message.guild.me.guild_permissions.moderate_members:
                        if message.guild.me.top_role > message.author.top_role:
                            if not message.author.guild_permissions.administrator:
                                await message.author.timeout_for(timedelta(minutes=1))
                                await message.channel.send(f"{message.author.mention} has been muted for spamming.")
                except:
                    pass

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    global sniped_message
    if message.author.bot:
        return
    sniped_message = (message.content, message.author)

@bot.command()
async def menu(ctx):
    embed = discord.Embed(
        title="Bot Commands",
        color=0x2f3136
    )
    embed.add_field(
        name="Moderation",
        value="!ban\n!unban\n!kick\n!mute\n!unmute\n!clear\n!warn\n!warnings\n!nick\n!role\n!removerole\n!nuke",
        inline=False
    )
    embed.add_field(
        name="Protection",
        value="!antilink on/off\n!antispam on/off\n!lock\n!unlock\n!slowmode",
        inline=False
    )
    embed.add_field(
        name="System",
        value="!admin\n!unadmin\n!autorole\n!welcome\n!log-channel\n!afk\n!snipe",
        inline=False
    )
    embed.add_field(
        name="Other",
        value="!announce\n!say\n!poll\n!avatar\n!userinfo\n!serverinfo\n!ping\n!list-admin\n!list-server\n!id",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"{round(bot.latency * 1000)}ms")

@bot.command()
async def admin(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return
    admins.add(member.id)
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"{member.mention} is now a bot admin.")

@bot.command()
async def unadmin(ctx, member: discord.Member):
    if ctx.author.id != OWNER_ID:
        return
    admins.discard(member.id)
    data["admins"] = list(admins)
    save_data(data)
    await ctx.send(f"Removed bot admin permissions from {member.mention}.")

@bot.command()
async def ban(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        return
    
    if not ctx.guild.me.guild_permissions.ban_members:
        await ctx.send("Error: I lack system permissions to execute this command. Please grant Ban Members or Administrator permissions to my role.")
        return
        
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"Error: Cannot ban {member.name}. My highest role is lower than or equal to this user's highest role.")
        return

    try:
        await member.ban()
        await ctx.send(f"Successfully banned {member.mention}.")
    except Exception as e:
        await ctx.send(f"Error: Discord system blocked this action. Details: {e}")

@bot.command()
async def unban(ctx, user_id: int):
    if not is_admin(ctx.author):
        return
        
    if not ctx.guild.me.guild_permissions.ban_members:
        await ctx.send("Error: I lack system permissions to execute this command. Please grant Ban Members or Administrator permissions.")
        return

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"Successfully unbanned {user.name}.")
    except Exception as e:
        await ctx.send(f"Error: Failed to unban. Details: {e}")

@bot.command()
async def kick(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        return
        
    if not ctx.guild.me.guild_permissions.kick_members:
        await ctx.send("Error: I lack system permissions to execute this command. Please grant Kick Members or Administrator permissions.")
        return
        
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"Error: Cannot kick {member.name}. My highest role is lower than or equal to this user's highest role.")
        return

    try:
        await member.kick()
        await ctx.send(f"Successfully kicked {member.mention}.")
    except Exception as e:
        await ctx.send(f"Error: Discord system blocked this action. Details: {e}")

@bot.command()
async def mute(ctx, member: discord.Member, time):
    if not is_admin(ctx.author):
        return
        
    if not ctx.guild.me.guild_permissions.moderate_members:
        await ctx.send("Error: I lack system permissions. Please grant Moderate Members or Administrator permissions.")
        return
        
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"Error: Cannot mute {member.name}. My highest role is lower than or equal to this user's highest role.")
        return

    if member.guild_permissions.administrator:
        await ctx.send(f"Error: Cannot mute {member.name}. System moderation actions cannot be applied to users with Administrator permissions.")
        return

    try:
        unit = time[-1]
        amount = int(time[:-1])
        if unit == "s":
            seconds = amount
        elif unit == "m":
            seconds = amount * 60
        elif unit == "h":
            seconds = amount * 3600
        elif unit == "d":
            seconds = amount * 86400
        else:
            await ctx.send("Invalid format. Usage example: !mute @user 10m (s/m/h/d)")
            return
            
        await member.timeout_for(timedelta(seconds=seconds))
        await ctx.send(f"Muted {member.mention} for {time}.")
    except ValueError:
        await ctx.send("Time format error. Amount must be a positive integer.")
    except Exception as e:
        await ctx.send(f"Error: Discord system blocked this action. Details: {e}")

@bot.command()
async def unmute(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        return
        
    if not ctx.guild.me.guild_permissions.moderate_members:
        await ctx.send("Error: I lack system permissions. Please grant Moderate Members to lift timeouts.")
        return
        
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"Error: Failed to unmute. My role is lower than or equal to {member.name}.")
        return

    try:
        await member.timeout(None)
        await ctx.send(f"Successfully unmuted {member.mention}.")
    except Exception as e:
        await ctx.send(f"Error: Unable to lift timeout. Details: {e}")

@bot.command(name="clear")
async def clear(ctx, amount: int):
    if not is_admin(ctx.author):
        return
    if amount > 1000:
        return
    try:
        await ctx.channel.purge(limit=amount + 1)
    except:
        pass

@bot.command()
async def warn(ctx, member: discord.Member):
    if not is_admin(ctx.author):
        return
    user_id = str(member.id)
    if user_id not in warnings:
        warnings[user_id] = 0
    warnings[user_id] += 1
    data["warnings"] = warnings
    save_data(data)
    
    await ctx.send(f"{member.mention} has been warned. Total warnings: {warnings[user_id]}.")
    
    if warnings[user_id] == 3:
        try:
            await member.timeout_for(timedelta(hours=1))
            await ctx.send(f"{member.mention} has been automatically muted for 1 hour (3 warnings).")
        except:
            pass
    elif warnings[user_id] == 5:
        try:
            await member.timeout_for(timedelta(hours=4))
            await ctx.send(f"{member.mention} has been automatically muted for 4 hours (5 warnings).")
        except:
            pass
    elif warnings[user_id] == 10:
        try:
            await member.timeout_for(timedelta(days=1))
            await ctx.send(f"{member.mention} has been automatically muted for 1 day (10 warnings).")
        except:
            pass

@bot.command()
async def warnings(ctx, member: discord.Member):
    user_id = str(member.id)
    count = warnings.get(user_id, 0)
    await ctx.send(f"{member.mention} has {count} warning(s).")

@bot.command()
async def nick(ctx, member: discord.Member, *, name):
    if not is_admin(ctx.author):
        return
    try:
        await member.edit(nick=name)
        await ctx.send(f"Changed nickname for {member.mention}.")
    except:
        await ctx.send("Failed to change nickname.")

@bot.command()
async def role(ctx, member: discord.Member, *, role: discord.Role):
    if not is_admin(ctx.author):
        return
    try:
        await member.add_roles(role)
        await ctx.send(f"Added role {role.name} to {member.mention}.")
    except Exception as e:
        print(f"Role Command Error: {e}")
        await ctx.send("Failed to add role. Check bot's role hierarchy or permissions.")

@bot.command()
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    if not is_admin(ctx.author):
        return
    try:
        await member.remove_roles(role)
        await ctx.send(f"Removed role {role.name} from {member.mention}.")
    except Exception as e:
        print(f"Removerole Command Error: {e}")
        await ctx.send("Failed to remove role. Make sure my role is higher.")

@bot.command()
async def lock(ctx):
    if not is_admin(ctx.author):
        return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("This channel has been locked.")

@bot.command()
async def unlock(ctx):
    if not is_admin(ctx.author):
        return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("This channel has been unlocked.")

@bot.command()
async def slowmode(ctx, seconds: int):
    if not is_admin(ctx.author):
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"Slowmode set to {seconds} seconds.")

@bot.command()
async def say(ctx, *, text):
    if not is_admin(ctx.author):
        return
    try:
        await ctx.message.delete()
    except:
        pass
    await ctx.send(text)

@bot.command()
async def announce(ctx, *, text):
    if not is_admin(ctx.author):
        return
    try:
        await ctx.message.delete()
    except:
        pass
    embed = discord.Embed(title="Announcement", description=text, color=0x2f3136)
    await ctx.send(embed=embed)

@bot.command()
async def nuke(ctx, channel: discord.TextChannel):
    if not is_admin(ctx.author):
        return
    try:
        new_channel = await channel.clone(reason="Nuke channel execution")
        await new_channel.edit(position=channel.position)
        await channel.delete()
        await new_channel.send("This channel has been nuked and recreated!")
    except Exception as e:
        await ctx.send(f"Failed to nuke channel: {e}")

@bot.command()
async def poll(ctx, question, choice1, choice2):
    try:
        await ctx.message.delete()
    except:
        pass
    embed = discord.Embed(title="Poll / Voting", description=question, color=0x2f3136)
    embed.add_field(name="Choice 1", value=f"1️⃣ {choice1}", inline=False)
    embed.add_field(name="Choice 2", value=f"2️⃣ {choice2}", inline=False)
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("1️⃣")
    await msg.add_reaction("2️⃣")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    if not member:
        member = ctx.author
    await ctx.send(member.display_avatar.url)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    if not member:
        member = ctx.author
    embed = discord.Embed(title=member.name, color=0x2f3136)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Created At", value=member.created_at.date())
    embed.add_field(name="Joined At", value=member.joined_at.date())
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=0x2f3136)
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    await ctx.send(embed=embed)

@bot.command()
async def autorole(ctx, role: discord.Role):
    global autorole
    if not is_admin(ctx.author):
        return
    autorole = role.id
    data["autorole"] = autorole
    save_data(data)
    await ctx.send(f"Autorole has been set to {role.mention}.")

@bot.command()
async def welcome(ctx, channel: discord.TextChannel):
    global welcome_channel
    if not is_admin(ctx.author):
        return
    welcome_channel = channel.id
    data["welcome_channel"] = welcome_channel
    save_data(data)
    await ctx.send(f"Welcome channel has been set to {channel.mention}.")

@bot.command(name="log-channel")
async def log_channel_cmd(ctx, channel: discord.TextChannel):
    global log_channel
    if not is_admin(ctx.author):
        return
    log_channel = channel.id
    data["log_channel"] = log_channel
    save_data(data)
    await ctx.send(f"Log channel has been set to {channel.mention}.")

@bot.command()
async def afk(ctx, *, reason="AFK"):
    afk_users[str(ctx.author.id)] = reason
    data["afk_users"] = afk_users
    save_data(data)
    await ctx.send(f"{ctx.author.mention} is now AFK.")

@bot.command()
async def snipe(ctx):
    global sniped_message
    if not sniped_message:
        return
    content, author = sniped_message
    await ctx.send(f"{author.name}: {content}")

@bot.command()
async def antilink(ctx, mode):
    global anti_link
    if not is_admin(ctx.author):
        return
    if mode.lower() == "on":
        anti_link = True
    elif mode.lower() == "off":
        anti_link = False
    else:
        return
    data["anti_link"] = anti_link
    save_data(data)
    await ctx.send(f"Anti-link feature turned {mode.upper()}.")

@bot.command()
async def antispam(ctx, mode):
    global anti_spam
    if not is_admin(ctx.author):
        return
    if mode.lower() == "on":
        anti_spam = True
    elif mode.lower() == "off":
        anti_spam = False
    else:
        return
    data["anti_spam"] = anti_spam
    save_data(data)
    await ctx.send(f"Anti-spam feature turned {mode.upper()}.")

@bot.command(name="list-server")
async def list_server(ctx):
    await ctx.send("\n".join([g.name for g in bot.guilds]))

@bot.command(name="list-admin")
async def list_admin(ctx):
    await ctx.send(", ".join([str(i) for i in admins]))

@bot.command(name="id")
async def get_id(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"{member.name}'s ID: {member.id}")

keep_alive()

bot.run(os.getenv("TOKEN"))
