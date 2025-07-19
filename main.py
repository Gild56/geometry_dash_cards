import os
import sys
import json
import random
import asyncio
import nest_asyncio
from typing import Any
from datetime import datetime
from telegram import Update, InputFile, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler


with open("secret.key", "rb") as key_file:
    key = key_file.read()

TOKEN = key.decode("utf-8").strip()
DATA_FILE = "users_data.json"
CARDS_FILE = "cards.json"
IMAGES_FOLDER = "resources/images"
COOLDOWN_MINUTES = 30

RARITIES = {
    "mythic": "🔴 Mythic",
    "legendary": "🟠 Legendary",
    "epic": "🟡 Epic",
    "rare": "🟢 Rare",
    "common": "🔵 Common",
}

RARITY_POINTS = {
    "common": 1,
    "rare": 2,
    "epic": 3,
    "legendary": 4,
    "mythic": 5,
}

data_lock = asyncio.Lock()
last_card_usage = {}
cooldown_lock = asyncio.Lock()
cards_data = {}


def load_all_cards():
    global cards_data
    try:
        with open(CARDS_FILE, "r") as f:
            cards_data = json.load(f)
    except FileNotFoundError:
        cards_data = {}


def load_data() -> dict[str, dict[str, Any]]:
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except FileNotFoundError:
        return {}


def save_data(data: dict[str, dict[str, Any]]):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def safe_load_data() -> dict[str, dict[str, Any]]:
    async with data_lock:
        return load_data()


async def safe_save_data(data: dict[str, dict[str, Any]]):
    async with data_lock:
        save_data(data)


async def reply(update: Update, text: str, **kwargs):
    if update.message:
        await update.message.reply_text(text, **kwargs)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, **kwargs)


async def reply_photo(update: Update, photo, **kwargs):
    if update.message:
        await update.message.reply_photo(photo, **kwargs)
    elif update.callback_query:
        await update.callback_query.message.reply_photo(photo, **kwargs)


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    data = await safe_load_data()

    if user_id not in data:
        data[user_id] = {
            "username": user.username or user.first_name,
            "cards": [],
            "points": 0
        }
        await safe_save_data(data)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("About the bot", callback_data="info")],
            [InlineKeyboardButton("Unlock a card", callback_data="card")],
            [InlineKeyboardButton("View your collection", callback_data="collection")],
            [InlineKeyboardButton("View your profile", callback_data="profile")],
            [InlineKeyboardButton("Leaderboard", callback_data="leaderboard")]
        ])
        await update.message.reply_text(f"Welcome {data[user_id]['username']}! Your account was successfully created.", reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text("You already have an account!")


# /info
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, "It is the Geometry Dash Cards bot.\n/card unlocks a card\n/collection shows your collection\n/collecion <username> shows someone's collection\n/profile shows your profile\n/profile <username> shows someone's profile\n/info shows bot's description\n/leaderboard shows the leaderboard\n\nAutor: @Gild56 | [YouTube](https://youtube.com/@gild56gmd)\n[GildHub page](https://github.com/Gild56/geometry_dash_cards)", parse_mode="Markdown")


# /card
async def card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    now = datetime.now()

    async with cooldown_lock:
        last_used = last_card_usage.get(user_id)
        if last_used:
            elapsed = (now - last_used).total_seconds() / 60
            if elapsed < COOLDOWN_MINUTES:
                remaining = int(COOLDOWN_MINUTES - elapsed) + 1
                await reply(update,
                    f"Please wait {remaining} more minutes before using /card again."
                )
                return

    data = await safe_load_data()
    if user_id not in data:
        await reply(update, "Do /start to create an account first.")
        return

    owned_cards = set(data[user_id]["cards"])

    available_cards = [
        (rarity, card)
        for rarity, cards in cards_data.items()
        for card in cards
        if card not in owned_cards
    ]

    if not available_cards:
        await reply(update, "You already have all the cards!")
        return

    last_card_usage[user_id] = now

    rarity, card = random.choice(available_cards)
    card_info = cards_data[rarity][card]
    description = card_info["description"]
    if not description:
        description = "No description available"
    link = card_info["link"]

    data[user_id]["cards"].append(card)
    data[user_id]["points"] += RARITY_POINTS.get(rarity, 0)
    await safe_save_data(data)

    image_path = os.path.join(IMAGES_FOLDER, f"{card}.png")

    rarity_display = f"{RARITIES.get(rarity, rarity.title())} ({RARITY_POINTS.get(rarity, 0)} points)"
    caption = f"*{card}*\n\n*Rarity: {rarity_display}*\n\n{description}"
    if link:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("\u25b6\ufe0f Link", url=link)]
        ])
    else:
        keyboard = None

    if os.path.exists(image_path):
        with open(image_path, "rb") as img:
            await reply_photo(update, photo=InputFile(img), caption=caption, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await reply(update, caption, parse_mode="Markdown", reply_markup=keyboard)


# /collection [card name]
async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await reply(update, "Do /start to create an account first.")
        return

    user_cards = data[user_id]["cards"]

    try:
        with open(CARDS_FILE, "r") as f:
            cards_data = json.load(f)
    except FileNotFoundError:
        await reply(update, "Card database not found.")
        return

    if context.args:
        card_name = " ".join(context.args)

        for rarity, cards in cards_data.items():
            if card_name in cards:
                if card_name in user_cards:
                    description = cards[card_name]["description"]
                    if not description:
                        description = "No description available"
                    link = cards[card_name]["link"]
                    image_path = os.path.join(IMAGES_FOLDER, f"{card_name}.png")
                    rarity_display = RARITIES.get(rarity, rarity.title())
                    caption = f"*{card_name}*\n\n*Rarity: {rarity_display}*\n\n{description}"

                    if link:
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("\u25b6\ufe0f Link", url=link)]
                        ])
                    else:
                        keyboard = None

                    if os.path.exists(image_path):
                        with open(image_path, "rb") as img:
                            await reply_photo(update, photo=InputFile(img), caption=caption, parse_mode="Markdown", reply_markup=keyboard)
                    else:
                        await reply(update, caption, parse_mode="Markdown", reply_markup=keyboard)
                else:
                    await reply(update, "You don't own this card.")
                return

        await reply(update, "This card doesn't exist.")
        return

    rarity_order = ["mythic", "legendary", "epic", "rare", "common"]
    sorted_collection = []
    total_owned = 0
    total_available = 0

    for rarity in rarity_order:
        all_cards = list(cards_data.get(rarity, {}).keys())
        owned_cards = sorted([card for card in all_cards if card in user_cards])
        count_owned = len(owned_cards)
        count_total = len(all_cards)

        total_owned += count_owned
        total_available += count_total

        if count_total > 0:
            percentage = (count_owned / count_total) * 100
            cards_with_desc = [
                f"• [{card}](https://t.me/{context.bot.username}?text=%2Fcollection%20{card.replace(' ', '%20')})"
                for card in owned_cards
            ]
            cards_text = "\n".join(cards_with_desc) if cards_with_desc else "None"
            sorted_collection.append(
                f"*{RARITIES.get(rarity, rarity.title())}* ({count_owned}/{count_total} - {percentage:.1f}%):\n{cards_text}"
            )

    global_percentage = (total_owned / total_available) * 100 if total_available > 0 else 0
    summary = f"*Total*: {total_owned}/{total_available} cards ({global_percentage:.1f}% complete) ({data[user_id]["points"]} points)\n"

    response = str(summary + "\n\n" + "\n\n".join(sorted_collection))
    await reply(update, response, parse_mode="Markdown")


# /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    if not data:
        await reply(update, "No players found.")
        return

    leaderboard_list = [
        (
            info.get("username", "Unknown"),
            len(info.get("cards", [])),
            info.get("points", 0)
        )
        for info in data.values()
    ]

    leaderboard_list.sort(key=lambda x: x[2], reverse=True)

    top = leaderboard_list[:10]
    message = "*Leaderboard - Top 10 Players*\n\n"

    for i, (username, card_count, points) in enumerate(top, start=1):
        message += f"{i}. [{username}](https://t.me/{context.bot.username}?text=%2Fprofile%20{username.replace(' ', '%20')}): {card_count} cards, {points} pts\n"
    await reply(update, message, parse_mode="Markdown")


# /profile [username]
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    sender_id = str(update.effective_user.id)
    target_username = " ".join(context.args).strip().lower() if context.args else None

    target_data = None

    for uid, info in data.items():
        if target_username:
            if info.get("username", "").lower() == target_username:
                target_data = info
                break
        else:
            if uid == sender_id:
                target_data = info
                break

    if not target_data:
        await reply(update, "User not found. Make sure they have used /start.")
        return

    leaderboard = sorted(
        data.values(),
        key=lambda x: x.get("points", 0),
        reverse=True
    )
    rank = leaderboard.index(target_data) + 1
    total_cards = sum(len(cards) for cards in cards_data.values())

    username = target_data.get("username", "Unknown")
    card_count = len(target_data.get("cards", []))
    points = target_data.get("points", 0)

    button_username = username.replace(" ", "%20")
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("View Collection", url=f"https://t.me/{context.bot.username}?start=collection%20{button_username}")
    ]])

    await reply(update, 
        f"*Profile of {username}* (@{username}):\n"
        f"Top: #{rank}\n"
        f"Cards: {card_count}/{total_cards}\n"
        f"Points: {points}",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "info":
        await info(update, context)
    elif query.data == "card":
        await card(update, context)
    elif query.data == "collection":
        await collection(update, context)
    elif query.data == "profile":
        await profile(update, context)
    elif query.data == "leaderboard":
        await leaderboard(update, context)



async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("card", "Unlock a card"),
        BotCommand("info", "Informations about the bot"),
        BotCommand("collection", "See your collection"),
        BotCommand("leaderboard", "See the leaderboard"),
        BotCommand("profile", "See your profile or someone else's"),
        BotCommand("start", "Create an account"),
    ])


async def main():
    load_all_cards()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("card", card))
    app.add_handler(CommandHandler("collection", collection))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CallbackQueryHandler(handle_button))


    asyncio.create_task(set_bot_commands(app))

    print("Running the bot...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        print(f"Error in the execution : {e}", file=sys.stderr)
