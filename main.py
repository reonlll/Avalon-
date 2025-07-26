import discord
from discord.ext import commands
from discord import app_commands
import os
import requests
import random
from discord.ui import View, Button
from keep_alive import keep_alive
import datetime

# Intent設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Bot・CommandTreeの定義
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
GUILD_ID = 1389167820553588797  # あなたのサーバーIDに置き換え済み

# jsonbin.io 設定
BALANCE_BIN_ID = "685190308960c979a5ab83e4"
API_KEY = "$2a$10$DUY6hRZaDGFQ1O6ddUbZpuDZY/k0xEA6iX69Ec2Qgc5Y4Rnihr9iO"
balance_data = {}

def load_balance_data():
    url = f"https://api.jsonbin.io/v3/b/{BALANCE_BIN_ID}/latest"
    headers = {"X-Master-Key": API_KEY}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        global balance_data
        balance_data = res.json()["record"]
    else:
        print("❌ 残高データの読み込み失敗")

def save_balance_data():
    url = f"https://api.jsonbin.io/v3/b/{BALANCE_BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": API_KEY
    }
    requests.put(url, headers=headers, json=balance_data)

# 起動時処理
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ スラッシュコマンド同期完了: {bot.user}")

# /残高
@tree.command(name="残高", description="自分の所持GOLDを確認します", guild=discord.Object(id=GUILD_ID))
async def check_balance(interaction: discord.Interaction):
    load_balance_data()
    user_id = str(interaction.user.id)
    balance = balance_data.get(user_id, 0)
    await interaction.response.send_message(
        f"💰 {interaction.user.mention} の残高: {balance:,} GOLD", ephemeral=True
    )

# /送金
@tree.command(name="送金", description="他のユーザーにgoldを送ります", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="送金先ユーザー", amount="送る金額")
async def send_gold(interaction: discord.Interaction, user: discord.User, amount: int):
    load_balance_data()
    sender_id = str(interaction.user.id)
    receiver_id = str(user.id)

    if amount <= 0:
        await interaction.response.send_message("⚠️ 金額は1以上にしてください", ephemeral=True)
        return
    if balance_data.get(sender_id, 0) < amount:
        await interaction.response.send_message("💸 所持goldが足りません", ephemeral=True)
        return

    balance_data[sender_id] -= amount
    balance_data[receiver_id] = balance_data.get(receiver_id, 0) + amount
    save_balance_data()

    await interaction.response.send_message(
        f"✅ {amount:,} gold を {user.mention} に送金しました！", ephemeral=True
    )

# /gold付与（管理者）
@tree.command(name="gold付与", description="ユーザーにGOLDを付与（管理者限定）", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="対象ユーザー", amount="付与する金額")
async def add_gold(interaction: discord.Interaction, user: discord.User, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
        return

    load_balance_data()
    user_id = str(user.id)
    balance_data[user_id] = balance_data.get(user_id, 0) + amount
    save_balance_data()

    await interaction.response.send_message(
        f"✅ {user.mention} に {amount:,} gold を付与しました", ephemeral=True
    )

# /gold減少（管理者）
@tree.command(name="gold減少", description="ユーザーのGOLDを減らす（管理者限定）", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="対象ユーザー", amount="減らす金額")
async def subtract_gold(interaction: discord.Interaction, user: discord.User, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
        return

    load_balance_data()
    user_id = str(user.id)
    balance_data[user_id] = max(balance_data.get(user_id, 0) - amount, 0)
    save_balance_data()

    await interaction.response.send_message(
        f"💸 {user.mention} から {amount:,} gold を減らしました", ephemeral=True
    )

# --- おみくじコマンド（/運勢） ---
last_fortune = {}
fortunes = [
    ("🌟 大吉", "最高の一日になる予感！", 3000),
    ("😊 中吉", "いいことがあるかもね。", 1000),
    ("🙂 小吉", "まあまあ良い感じ。", 0),
    ("😐 末吉", "ゆっくりいこう。", 0),
    ("😑 凶", "今日は慎重にね。", 0),
    ("💀 大凶", "今日は静かに過ごそう…", 0)
]

@tree.command(name="運勢", description="今日の運勢を占おう！", guild=discord.Object(id=GUILD_ID))
async def fortune(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    today = datetime.datetime.now().date()

    if user_id in last_fortune and last_fortune[user_id] == today:
        await interaction.response.send_message("🔁 今日の運勢はすでに引きました！また明日！", ephemeral=True)
        return

    result, message, reward = random.choice(fortunes)
    last_fortune[user_id] = today

    load_balance_data()
    if user_id not in balance_data:
        balance_data[user_id] = 0
    balance_data[user_id] += reward
    save_balance_data()

    reply = f"🎴 あなたの今日の運勢：**{result}**\n💬 {message}"
    if reward > 0:
        reply += f"\n💰 {reward:,} GOLDを獲得しました！"

    await interaction.response.send_message(reply)

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))  # ギルド用だけ同期
    await tree.sync()  # すでにあるグローバルコマンドを同期

    # グローバルコマンドを削除
    global_cmds = await tree.fetch_commands()
    for cmd in global_cmds:
        await tree.remove_command(cmd.name)

    print(f"✅ グローバルコマンド削除完了")

# --- Bot起動 ---
keep_alive()
bot.run(os.environ["TOKEN"])