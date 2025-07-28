import discord
from discord.ext import commands
from discord import app_commands
import os
import requests
import random
from discord.ui import View, Button
from keep_alive import keep_alive
import datetime

# ロール保存用
ROLE_BIN_ID = "6851e9728960c979a5abb516"
user_owned_roles = {}

def load_user_roles():
    url = f"https://api.jsonbin.io/v3/b/{ROLE_BIN_ID}/latest"
    headers = {"X-Master-Key": API_KEY}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        global user_owned_roles
        user_owned_roles = res.json()["record"]
    else:
        print("❌ ロールデータの読み込み失敗")

def save_user_roles():
    url = f"https://api.jsonbin.io/v3/b/{ROLE_BIN_ID}"
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": API_KEY
    }
    requests.put(url, headers=headers, json=user_owned_roles)


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

class JankenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="✊", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process(interaction, "✊")

    @discord.ui.button(label="✌️", style=discord.ButtonStyle.success)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process(interaction, "✌️")

    @discord.ui.button(label="✋", style=discord.ButtonStyle.danger)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process(interaction, "✋")

    async def process(self, interaction: discord.Interaction, user_hand):
        load_balance_data()  # ← 追加：残高読み込み

        user_id = str(interaction.user.id)
        bot_hand = random.choice(["✊", "✌️", "✋"])

        # GOLDが3000未満ならキャンセル
        if balance_data.get(user_id, 0) < 3000:
            await interaction.response.send_message("❌ 所持GOLDが足りません（3000GOLD必要）", ephemeral=True)
            return

        # 勝敗判定
        if user_hand == bot_hand:
            result = f"🤝 あいこでした！（Botの手：{bot_hand}）"
        elif (user_hand, bot_hand) in [("✊", "✌️"), ("✌️", "✋"), ("✋", "✊")]:
            balance_data[user_id] += 3000
            result = f"🎉 あなたの勝ち！+3000GOLD！（Botの手：{bot_hand}）"
        else:
            balance_data[user_id] -= 3000
            result = f"😢 負けてしまいました... -3000GOLD（Botの手：{bot_hand}）"

        save_balance_data()
        await interaction.response.send_message(result, ephemeral=True)
        
        # --- /じゃんけんコマンド登録 ---
@tree.command(name="じゃんけん", description="3000GOLDを賭けてBotとじゃんけん！", guild=discord.Object(id=GUILD_ID))
async def janken(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🕹️ グー・チョキ・パーから選んでください！",
        view=JankenView(),
        ephemeral=True
    )

ROLL_GACHA_LIST = [
    "旅人", "みかん🍊", "じぽ", "草ww", "騎士",
    "泥棒", "ドラゴンボール信者", "ネタ枠", "暗黒騎士", "53"
]

class RoleGachaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # 永続ボタン

    @discord.ui.button(label="🎲 ロールガチャを引く！", style=discord.ButtonStyle.primary)
    async def roll_gacha(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        load_balance_data()
        load_user_roles()

        if balance_data.get(user_id, 0) < 30000:
            await interaction.response.send_message("💰 30000GOLDが必要です。", ephemeral=True)
            return

        balance_data[user_id] -= 30000
        result = random.choice(ROLL_GACHA_LIST)
        user_owned_roles.setdefault(user_id, [])
        if result not in user_owned_roles[user_id]:
            user_owned_roles[user_id].append(result)

        save_balance_data()
        save_user_roles()

        await interaction.response.send_message(f"🎉 ガチャ結果：**{result}** を獲得しました！", ephemeral=True)
        
@tree.command(name="ロールガチャ設置", description="ロールガチャのボタンを設置（管理者限定）", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="ガチャボタンを設置するチャンネル")
async def setup_gacha_button(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 管理者専用コマンドです。", ephemeral=True)
        return

    view = RoleGachaView()
    await channel.send("🎰 **ロールガチャ** に挑戦！ボタンを押して運試ししよう！（30000GOLD）", view=view)
    await interaction.response.send_message(f"✅ ガチャボタンを {channel.mention} に設置しました！", ephemeral=True)


@tree.command(name="ロールガチャ", description="30000GOLDを消費してランダムなロールを獲得", guild=discord.Object(id=GUILD_ID))
async def roll_gacha(interaction: discord.Interaction):
    load_balance_data()
    load_user_roles()
    user_id = str(interaction.user.id)

    if balance_data.get(user_id, 0) < 30000:
        await interaction.response.send_message("❌ 所持GOLDが足りません（30000GOLD必要）", ephemeral=True)
        return

    balance_data[user_id] -= 30000
    save_balance_data()

    selected_role = random.choice(ROLL_GACHA_LIST)
    user_owned_roles.setdefault(user_id, [])
    if selected_role not in user_owned_roles[user_id]:
        user_owned_roles[user_id].append(selected_role)
        save_user_roles()

    await interaction.response.send_message(
        f"🎉 ガチャ結果：**{selected_role}**\nロール一覧で確認できます！",
        ephemeral=True
    )


@tree.command(name="ロール一覧", description="自分が所持しているロールを確認", guild=discord.Object(id=GUILD_ID))
async def list_roles(interaction: discord.Interaction):
    load_user_roles()
    user_id = str(interaction.user.id)
    roles = user_owned_roles.get(user_id, [])
    if not roles:
        await interaction.response.send_message("🎭 まだロールを獲得していません。", ephemeral=True)
    else:
        await interaction.response.send_message("🎭 あなたの所持ロール：\n" + ", ".join(roles), ephemeral=True)


from discord import app_commands

# 🔄 オートコンプリート補助関数（必ず async def にする）
async def autocomplete_owned_roles(interaction: discord.Interaction, current: str):
    load_user_roles()
    user_id = str(interaction.user.id)
    roles = user_owned_roles.get(user_id, [])
    return [
        app_commands.Choice(name=r, value=r)
        for r in roles if current.lower() in r.lower()
    ][:25]  # 最大25件まで補完

# 🎁 ロール付与コマンド（補完付き）
@tree.command(name="ロール付与", description="所持しているロールの中から1つを自分に付与", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role_name="付与するロール名")
@app_commands.autocomplete(role_name=autocomplete_owned_roles)  # 🔄 修正済み！
async def give_role(interaction: discord.Interaction, role_name: str):
    load_user_roles()
    user_id = str(interaction.user.id)
    roles = user_owned_roles.get(user_id, [])

    if role_name not in roles:
        await interaction.response.send_message("❌ そのロールは所持していません。", ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, name=role_name)
    if role:
        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"✅ {role_name} を付与しました！", ephemeral=True)
    else:
        await interaction.response.send_message("❌ サーバーにそのロールが存在しません。", ephemeral=True)


@tree.command(name="ロール外し", description="自分のロールを外します（所持情報は保持）", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role_name="外すロール名")
async def remove_role(interaction: discord.Interaction, role_name: str):
    role = discord.utils.get(interaction.guild.roles, name=role_name)
    if role and role in interaction.user.roles:
        await interaction.user.remove_roles(role)
        await interaction.response.send_message(f"✅ {role_name} を外しました。", ephemeral=True)
    else:
        await interaction.response.send_message("❌ そのロールは現在付与されていません。", ephemeral=True)


@tree.command(name="ロールを捨てる", description="所持しているロールを完全に削除", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role_name="削除するロール名")
async def drop_role(interaction: discord.Interaction, role_name: str):
    load_user_roles()
    user_id = str(interaction.user.id)
    roles = user_owned_roles.get(user_id, [])

    if role_name not in roles:
        await interaction.response.send_message("❌ そのロールは所持していません。", ephemeral=True)
        return

    roles.remove(role_name)
    user_owned_roles[user_id] = roles
    save_user_roles()
    await interaction.response.send_message(f"🗑️ {role_name} を削除しました。", ephemeral=True)

from discord import ui

class ShisumaView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_fingers = None

        for i in range(3):
            self.add_item(ShisumaFingerButton(label=f"{i}本", value=i, view=self))

class ShisumaFingerButton(discord.ui.Button):
    def __init__(self, label, value, view):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.value = value
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.main_view.user_id):
            await interaction.response.send_message("これはあなた専用のゲームです。", ephemeral=True)
            return

        self.main_view.user_fingers = self.value
        await interaction.response.send_message("🎯 合計の予想を選んでください", view=ShisumaGuessView(self.main_view.user_id, self.value), ephemeral=True)

class ShisumaGuessView(discord.ui.View):
    def __init__(self, user_id, user_fingers):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.user_fingers = user_fingers

        for i in range(5):
            self.add_item(ShisumaGuessButton(label=f"{i}", value=i, view=self))

class ShisumaGuessButton(discord.ui.Button):
    def __init__(self, label, value, view):
        super().__init__(label=label, style=discord.ButtonStyle.success)
        self.value = value
        self.main_view = view

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(self.main_view.user_id):
            await interaction.response.send_message("これはあなた専用のゲームです。", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        load_balance_data()

        if balance_data.get(user_id, 0) < 2000:
            await interaction.response.send_message("💰 2000GOLDが必要です。", ephemeral=True)
            return

        bot_fingers = random.randint(0, 2)
        total = self.main_view.user_fingers + bot_fingers
        guess = self.value

        result_msg = f"🧍‍♂️ あなたの指: {self.main_view.user_fingers}本\n🤖 Botの指: {bot_fingers}本\n🎯 合計: {total}（あなたの予想: {guess}）\n"

        if total == guess:
            balance_data[user_id] += 2000
            result_msg += "🎉 的中！+2000GOLD獲得！"
        else:
            balance_data[user_id] -= 2000
            result_msg += "💥 外れ！-2000GOLD失いました。"

        save_balance_data()
        await interaction.response.send_message(result_msg, ephemeral=True)

@tree.command(name="指スマ", description="指の本数と合計を予想してBotと勝負！（2000GOLD）", guild=discord.Object(id=GUILD_ID))
async def shisuma(interaction: discord.Interaction):
    await interaction.response.send_message("🖐️ まず出す指の本数を選んでください（0〜2）", view=ShisumaView(interaction.user.id), ephemeral=True)
        
# プレイヤーごとのPvPステート管理
pvp_sessions = {}

class PvPView(discord.ui.View):
    def __init__(self, attacker, defender):
        super().__init__(timeout=None)
        self.attacker = attacker
        self.defender = defender

    @discord.ui.button(label="⚔️ 攻撃", style=discord.ButtonStyle.danger)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = pvp_sessions.get((self.attacker.id, self.defender.id))
        if not session:
            await interaction.response.send_message("戦闘が見つかりません。", ephemeral=True)
            return

        if interaction.user != session["turn"]:
            await interaction.response.send_message("あなたのターンではありません。", ephemeral=True)
            return

        damage = random.randint(10, 25)
        target = session["defender"] if interaction.user == session["attacker"] else session["attacker"]
        session["hp"][target.id] -= damage

        msg = f"💥 {interaction.user.mention} が {target.mention} に **{damage}** ダメージ！\n"
        msg += f"🩸 {session['attacker'].mention}：{session['hp'][session['attacker'].id]} HP\n"
        msg += f"🩸 {session['defender'].mention}：{session['hp'][session['defender'].id]} HP\n"

        # 勝敗チェック
        if session["hp"][target.id] <= 0:
            msg += f"🏆 {interaction.user.mention} の勝利！"
            del pvp_sessions[(self.attacker.id, self.defender.id)]
            self.disable_all_items()
            await interaction.response.edit_message(content=msg, view=self)
        else:
            # ターン交代
            session["turn"] = target
            await interaction.response.edit_message(content=msg + f"\n🎯 次のターン：{target.mention}", view=self)

@tree.command(name="pvp", description="指定した相手とPvPバトルを開始する")
@app_commands.describe(opponent="対戦相手を選んでください")
async def pvp(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.bot or opponent == interaction.user:
        await interaction.response.send_message("無効な対戦相手です。", ephemeral=True)
        return

    attacker = interaction.user
    defender = opponent
    pvp_sessions[(attacker.id, defender.id)] = {
        "attacker": attacker,
        "defender": defender,
        "hp": {
            attacker.id: 100,
            defender.id: 100
        },
        "turn": attacker
    }

    view = PvPView(attacker, defender)
    await interaction.response.send_message(
        f"⚔️ {attacker.mention} vs {defender.mention} のバトル開始！\n🎯 最初のターン：{attacker.mention}",
        view=view
    )

@tree.command(name="コマンド一覧", description="登録済みのスラッシュコマンド一覧を表示")
async def show_commands(interaction: discord.Interaction):
    commands = await tree.fetch_commands(guild=discord.Object(id=GUILD_ID))
    await interaction.response.send_message("\n".join(f"/{cmd.name}" for cmd in commands))


# --- Bot起動 ---
keep_alive()
bot.run(os.environ["TOKEN"])