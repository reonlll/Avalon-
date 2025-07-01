import discord
from discord.ext import commands
from discord import app_commands
import os
import requests
from keep_alive import keep_alive
import random
from discord.ui import View,Button



# Intent設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

# Bot・CommandTreeの定義
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # これでOK

# あなたのサーバーID（ギルドコマンド同期用）
GUILD_ID = 1389167820553588797

# --- jsonbin設定 ---
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

# --- 起動時処理 ---
@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ スラッシュコマンド同期完了: {bot.user}")

# --- テスト用コマンド ---
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# --- /残高 ---
@tree.command(name="残高", description="自分の所持GOLDを確認します", guild=discord.Object(id=GUILD_ID))
async def check_balance(interaction: discord.Interaction):
    load_balance_data()
    user_id = str(interaction.user.id)
    balance = balance_data.get(user_id, 0)
    await interaction.response.send_message(
        f"💰 {interaction.user.mention} の残高: {balance:,} GOLD", ephemeral=True
    )

# --- /送金 ---
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

# --- /GOLD付与（管理者） ---
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

# --- /GOLD減少（管理者） ---
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

@tree.command(name="pvp", description="指定した相手とPvPバトルを開始します", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(opponent="対戦相手")
async def pvp(interaction: discord.Interaction, opponent: discord.User):
    if opponent.bot:
        await interaction.response.send_message("❌ Botとは対戦できません", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ 自分とは対戦できません", ephemeral=True)
        return

    hp_data = {interaction.user.id: 100, opponent.id: 100}
    view = PvPButton(attacker=interaction.user, defender=opponent, hp_data=hp_data, turn_owner_id=interaction.user.id)

    await interaction.response.send_message(
        content=f"⚔️ {interaction.user.display_name} vs {opponent.display_name} のバトルが始まった！\n🎮 {interaction.user.display_name} のターン！",
        view=view
    )


class PvPButton(View):
    def __init__(self, attacker, defender, hp_data, turn_owner_id):
        super().__init__(timeout=None)
        self.attacker = attacker
        self.defender = defender
        self.hp_data = hp_data
        self.turn_owner_id = turn_owner_id

    Button(label="攻撃", style=discord.ButtonStyle.red)
    async def attack(self, interaction: discord.Interaction, button: discord.Button):
        if interaction.user.id != self.turn_owner_id:
            await interaction.response.send_message("❌ あなたのターンではありません", ephemeral=True)
            return

        damage = random.randint(10, 20)
        self.hp_data[self.defender.id] -= damage
        attacker_name = interaction.user.display_name
        defender_name = self.defender.display_name
        remaining_hp = self.hp_data[self.defender.id]

        if remaining_hp <= 0:
            await interaction.response.edit_message(
                content=f"💥 {attacker_name} の攻撃！\n{defender_name} は {damage} ダメージを受けた\n\n🎉 {attacker_name} の勝利！",
                view=None
            )
            return

        # ターン交代
        self.turn_owner_id = self.defender.id
        self.attacker, self.defender = self.defender, self.attacker
        await interaction.response.edit_message(
            content=f"💥 {attacker_name} の攻撃！\n{defender_name} は {damage} ダメージを受けた\n\n🩸 {defender_name} の残りHP: {remaining_hp}\n🎮 次は {self.attacker.display_name} のターン！",
            view=self
        )


# --- Flaskで常時起動 ---
keep_alive()
bot.run(os.environ['TOKEN'])