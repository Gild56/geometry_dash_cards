import os
import json
import random
import asyncio
from telegram import Update, InputFile, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

with open("secret.key", "rb") as key_file:
    key = key_file.read()

TOKEN = key.decode("utf-8").strip()
DATA_FILE = "users_data.json"
CARDS_FILE = "cards-test.json"
IMAGES_FOLDER = "resources/images"

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


def load_data() -> dict[str, list[int]]:
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except FileNotFoundError:
        return {}


def save_data(data: dict[str, dict]):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cards() -> list[str]:
    try:
        with open(CARDS_FILE, "r") as f:
            data = json.load(f)
            all_names = []
            for rarity in data.values():
                all_names.extend(rarity.keys())
            return all_names
    except FileNotFoundError:
        return []


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    user_id = str(user.id)

    if user_id not in data:
        data[user_id] = {
            "username": user.username or user.first_name,
            "cards": [],
            "points": 0
        }
        save_data(data)
        await update.message.reply_text(f"Welcome {data[user_id]['username']}! Your account was successfully created.")
    else:
        await update.message.reply_text("You already have an account!")


# /info
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I'm the official Geometry Dash Cards bot. Do /card to unlock a card and /collection to see your collection of cards.")


# /card
async def card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("Do /start to create an account first.")
        return

    try:
        with open(CARDS_FILE, "r") as f:
            cards_data = json.load(f)
    except FileNotFoundError:
        await update.message.reply_text("There are no cards.")
        return

    owned_cards = set(data[user_id]["cards"])

    available_cards = [
        (rarity, card)
        for rarity, cards in cards_data.items()
        for card in cards
        if card not in owned_cards
    ]

    if not available_cards:
        await update.message.reply_text("You already have all the cards!")
        return

    rarity, card = random.choice(available_cards)
    description = cards_data[rarity][card]["description"]
    link = cards_data[rarity][card]["link"]

    data[user_id]["cards"].append(card)
    data[user_id]["points"] += RARITY_POINTS.get(rarity, 0)

    save_data(data)

    image_path = os.path.join(IMAGES_FOLDER, f"{card}.png")

    rarity_display = f"{RARITIES.get(rarity, rarity.title())} ({RARITY_POINTS.get(rarity, 0)} points)"
    caption = f"*{card}*\n\n*Rarity: {rarity_display}*\n\n{description}\n\n[Watch on YouTube]({link})"

    if os.path.exists(image_path):
        with open(image_path, "rb") as img:
            await update.message.reply_photo(photo=InputFile(img), caption=caption, parse_mode="Markdown")
    else:
        await update.message.reply_text(caption + " (no image available)", parse_mode="Markdown")


# /collection [card name]
async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        await update.message.reply_text("Do /start to create an account first.")
        return

    user_cards = data[user_id]["cards"]

    try:
        with open(CARDS_FILE, "r") as f:
            cards_data = json.load(f)
    except FileNotFoundError:
        await update.message.reply_text("Card database not found.")
        return

    if context.args:
        card_name = " ".join(context.args)

        for rarity, cards in cards_data.items():
            if card_name in cards:
                if card_name in user_cards:
                    description = cards[card_name]["description"]
                    link = cards[card_name]["link"]
                    image_path = os.path.join(IMAGES_FOLDER, f"{card_name}.png")
                    rarity_display = RARITIES.get(rarity, rarity.title())
                    caption = f"*{card_name}*\n\n*Rarity: {rarity_display}*\n\n{description}\n\n[Watch on YouTube]({link})"

                    if os.path.exists(image_path):
                        with open(image_path, "rb") as img:
                            await update.message.reply_photo(photo=InputFile(img), caption=caption, parse_mode="Markdown")
                    else:
                        await update.message.reply_text(caption + " (no image available)", parse_mode="Markdown")
                else:
                    await update.message.reply_text("You don't own this card.")
                return

        await update.message.reply_text("This card doesn't exist.")
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
    await update.message.reply_text(response, parse_mode="Markdown")


# /leaderboard
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if context.args:
        target_username = " ".join(context.args).strip().lower()

        for user_id, info in data.items():
            if info.get("username", "").lower() == target_username:
                try:
                    with open(CARDS_FILE, "r") as f:
                        cards_data = json.load(f)
                except FileNotFoundError:
                    await update.message.reply_text("Card database not found.")
                    return

                user_cards = info.get("cards", [])
                rarity_order = ["mythic", "legendary", "epic", "rare", "common"]
                sorted_collection = []
                total_owned = 0
                total_available = 0

                for rarity in rarity_order:
                    all_cards = list(cards_data.get(rarity, {}).keys())
                    owned = sorted([card for card in all_cards if card in user_cards])
                    count_owned = len(owned)
                    count_total = len(all_cards)

                    total_owned += count_owned
                    total_available += count_total

                    if count_total > 0:
                        percent = (count_owned / count_total) * 100
                        links = [
                            f"• {card}"
                            for card in owned
                        ]
                        cards_text = "\n".join(links) if links else "None"
                        sorted_collection.append(
                            f"*{RARITIES.get(rarity, rarity.title())}* ({count_owned}/{count_total} - {percent:.1f}%):\n{cards_text}"
                        )

                global_percent = (total_owned / total_available) * 100 if total_available > 0 else 0
                summary = f"*{info.get('username')}’s Collection* ({total_owned}/{total_available} cards - {global_percent:.1f}% complete)\nPoints: {info.get('points', 0)} pts\n"
                response = summary + "\n\n" + "\n\n".join(sorted_collection)

                await update.message.reply_text(response, parse_mode="Markdown")
                return

        await update.message.reply_text("Username not found.")
        return

    if not data:
        await update.message.reply_text("No players found.")
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
        message += f"{i}. [{username}](https://t.me/{context.bot.username}?text=%2Fleaderboard%20{username.replace(' ', '%20')}): {card_count} cards, {points} pts\n"
    await update.message.reply_text(message, parse_mode="Markdown")


async def set_bot_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Create an account"),
        BotCommand("info", "Informations about the bot"),
        BotCommand("card", "Pick a card"),
        BotCommand("collection", "See your collection"),
        BotCommand("leaderboard", "See the leaderboard"),
    ])

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("card", card))
    app.add_handler(CommandHandler("collection", collection))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    asyncio.create_task(set_bot_commands(app))

    print("Running the bot...")
    await app.run_polling()


if __name__ == "__main__":
    import sys

    async def safe_main():
        try:
            await main()
        except Exception as e:
            print(f"Erreur in the bot : {e}", file=sys.stderr)

    try:
        import nest_asyncio
        nest_asyncio.apply()

        loop = asyncio.get_event_loop()
        loop.create_task(safe_main())
        loop.run_forever()
    except Exception as e:
        print(f"Error in the execution : {e}", file=sys.stderr)
