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

def has_character(user_id: int, character_name: str) -> bool:
    """指定ユーザーがそのキャラを所持しているか確認"""
    return character_name in user_characters.get(str(user_id), [])

def load_character_data():
    global user_characters
    try:
        with open("characters.json", "r", encoding="utf-8") as f:
            user_characters = json.load(f)
    except FileNotFoundError:
        user_characters = {}

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

class PvPRequestView(discord.ui.View):
    def __init__(self, attacker, defender):
        super().__init__(timeout=60)
        self.attacker = attacker
        self.defender = defender

    @discord.ui.button(label="✅ 承諾", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.defender:
            await interaction.response.send_message("あなたへのリクエストではありません。", ephemeral=True)
            return

        # 対戦セッション作成
        pvp_sessions[(self.attacker.id, self.defender.id)] = {
            "attacker": self.attacker,
            "defender": self.defender,
            "hp": {
                self.attacker.id: 100,
                self.defender.id: 100
            },
            "turn": self.attacker
        }

        view = PvPView(self.attacker, self.defender)
        await interaction.message.edit(content=f"⚔️ {self.attacker.mention} vs {self.defender.mention} のバトル開始！\n🎯 最初のターン：{self.attacker.mention}", view=view)

    @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.defender:
            await interaction.response.send_message("あなたへのリクエストではありません。", ephemeral=True)
            return

        await interaction.message.edit(content="❌ 対戦リクエストは拒否されました。", view=None)

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

@tree.command(name="pvp", description="指定した相手とPvPバトルを開始する", guild=discord.Object(id=GUILD_ID))
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

damage = random.randint(10, 25)
is_critical = random.random() < 0.2
if is_critical:
    damage = int(damage * 1.5)

target = session["defender"] if interaction.user == session["attacker"] else session["attacker"]
session["hp"][target.id] -= damage

msg = f"💥 {interaction.user.mention} が {target.mention} に **{damage}** ダメージ！\n"
if is_critical:
    msg += "🔥 **クリティカルヒット！**\n"
msg += f"🩸 {session['attacker'].mention}：{render_hp_bar(session['hp'][session['attacker'].id])} ({session['hp'][session['attacker'].id]} HP)\n"
msg += f"🩸 {session['defender'].mention}：{render_hp_bar(session['hp'][session['defender'].id])} ({session['hp'][session['defender'].id]} HP)\n"


CHARACTER_DATA = {
    "ランスロット": {
        "max_hp": 120,
        "attack": 25,
        "defense": 20,
        "speed": 15,
        "skills": {
            "ホーリーブレード": {"pp": 3, "desc": "敵単体に大ダメージ（攻撃力×1.8）"},
            "騎士の誓い": {"pp": 2, "desc": "味方の防御+10（3ターン）"},
            "カウンター構え": {"pp": 2, "desc": "受けたダメージの50%を反射（1ターン）"},
            "最後の突撃": {"pp": 1, "desc": "HP半分以下時、攻撃力×2.5ダメージ"},
        }
    }
}

battles = {
    (attacker_id, defender_id): {
        "attacker": discord.Member,
        "defender": discord.Member,
        "hp": {user_id: 120, ...},
        "pp": {user_id: {"ホーリーブレード": 3, ...}},
        "turn": attacker,  # 現在のターン
        "character": {user_id: "ランスロット"},
    }
}

@tree.command(name="キャラ情報", description="育成中のキャラの詳細を表示")
async def show_active_character(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    # キャラが選ばれていない場合
    if user_id not in active_character:
        await interaction.response.send_message("⚠️ 育成中のキャラが設定されていません。", ephemeral=True)
        return

    char_name = active_character[user_id]

    # 所持確認
    if not has_character(user_id, char_name):
        await interaction.response.send_message("⚠️ そのキャラは所持していません。", ephemeral=True)
        return

    # ステータス表示
    data = character_status.get(user_id, {}).get(char_name)
    if not data:
        await interaction.response.send_message("⚠️ キャラデータが見つかりません。", ephemeral=True)
        return

    hp = data["current_hp"]
    level = data["level"]
    exp = data["exp"]
    pp_list = data["pp"]
    skills = CHARACTER_DATA[char_name]["skills"]

    msg = f"📘 **{char_name}** 情報\n"
    msg += f"🧬 レベル: {level} / 20\n"
    msg += f"💖 HP: {hp} / {CHARACTER_DATA[char_name]['max_hp']}\n"
    msg += f"✨ EXP: {exp}\n"
    msg += f"🔧 スキル:\n"

    for idx, skill in enumerate(skills):
        msg += f"　{skill['name']} (残り {pp_list[idx]}回 / 威力: {skill['power']})\n"

    await interaction.response.send_message(msg, ephemeral=True)
    
@tree.command(name="キャラ情報", description="育成中のキャラのステータスとスキルを確認する", guild=discord.Object(id=GUILD_ID))
async def character_info(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    # データ読み込み（例：JSONファイルやjsonbinから）
    load_character_data()

    if user_id not in user_characters:
        await interaction.response.send_message("❌ 現在育成中のキャラがいません。", ephemeral=True)
        return

    char = user_characters[user_id]
    name = char["name"]
    level = char["level"]
    exp = char["exp"]
    skills = char.get("skills", [])

    skill_text = "\n".join([f"・{s['name']}（PP: {s['pp']}）" for s in skills]) if skills else "（スキルなし）"

    embed = discord.Embed(title=f"🧝 キャラ情報：{name}", color=0x33ccff)
    embed.add_field(name="📈 レベル", value=str(level), inline=True)
    embed.add_field(name="🔋 経験値", value=f"{exp} / 100", inline=True)
    embed.add_field(name="🛠 スキル", value=skill_text, inline=False)



    await interaction.response.send_message(embed=embed, ephemeral=True)

DATA_FILE = "characters.json"

# データを読み込む
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": {}}, f, ensure_ascii=False, indent=4)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# データを保存する
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 例: ランスロットを追加
def add_lancelot(user_id):
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "current": "ランスロット",
            "characters": {
                "ランスロット": {
                    "level": 1,
                    "exp": 0,
                    "skills": [
                        {"name": "秘剣・幻影突き", "pp": 3},
                        {"name": "聖騎士の誓い", "pp": 2},
                        {"name": "光速斬り", "pp": 3},
                        {"name": "無双の刃", "pp": 1}
                    ]
                }
            }
        }
        save_data(data)
        print(f"✅ {user_id} にランスロットを付与しました。")

# 動作確認
add_lancelot("123456789012345678")

from discord import app_commands
import json
import discord

CHARACTER_FILE = "characters.json"

def load_character_data():
    with open(CHARACTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_character_data(data):
    with open(CHARACTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@tree.command(name="キャラ情報", description="現在育成中のキャラの情報を表示します")
async def char_info(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = load_character_data()

    if user_id not in data["users"]:
        await interaction.response.send_message("キャラが登録されていません。", ephemeral=True)
        return

    user_data = data["users"][user_id]
    char_name = user_data["current"]
    char_info = user_data["characters"][char_name]
    level = char_info["level"]
    exp = char_info["exp"]
    skills = char_info["skills"]

    skill_list = "\n".join([f"- {skill['name']} (使用可能数: {skill['pp']})" for skill in skills])

    embed = discord.Embed(
        title=f"🧬 {char_name} の情報",
        description=f"**Lv {level}** / EXP: {exp}\n\n**スキル一覧：**\n{skill_list}",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

def add_lancelot(user_id):
    data = load_character_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "current": "ランスロット",
            "characters": {
                "ランスロット": {
                    "level": 1,
                    "exp": 0,
                    "skills": [
                        {"name": "秘剣・幻影突き", "pp": 3},
                        {"name": "聖騎士の誓い", "pp": 2},
                        {"name": "光速斬り", "pp": 3},
                        {"name": "無双の刃", "pp": 1}
                    ]
                }
            }
        }
        save_character_data(data)
        
@tree.command(name="キャラ付与", description="指定したユーザーにキャラを付与します（管理者専用）")
@app_commands.describe(user="キャラを付与する相手", character="付与するキャラ名")
@app_commands.autocomplete(character=lambda interaction, current: character_autocomplete(current))
async def give_character(interaction: discord.Interaction, user: discord.Member, character: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("このコマンドは管理者専用です。", ephemeral=True)
        return

    valid_characters = ["ランスロット", "ガウェイン", "トリスタン", "パーシバル", "モードレッド"]

    if character not in valid_characters:
        await interaction.response.send_message(f"❌ 無効なキャラ名です。利用可能なキャラ: {', '.join(valid_characters)}", ephemeral=True)
        return

    user_id = str(user.id)
    if user_id not in character_data:
        character_data[user_id] = {"owned": []}

    if character in character_data[user_id]["owned"]:
        await interaction.response.send_message(f"{user.mention} はすでに {character} を所持しています。", ephemeral=True)
        return

    character_data[user_id]["owned"].append(character)
    save_character_data()

    await interaction.response.send_message(f"✅ {user.mention} に {character} を付与しました。")

@tree.command(name="コマンド一覧", description="登録済みのスラッシュコマンド一覧を表示")
async def show_commands(interaction: discord.Interaction):
    commands = await tree.fetch_commands(guild=discord.Object(id=GUILD_ID))
    await interaction.response.send_message("\n".join(f"/{cmd.name}" for cmd in commands))

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))  # ギルドID指定
    print(f"{bot.user} がログインしました。")

# --- Bot起動 ---
keep_alive()
bot.run(os.environ["TOKEN"])