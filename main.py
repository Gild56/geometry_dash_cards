import os
import json
import random
from telegram import Update, InputFile
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


def load_data() -> dict[str, list[int]]:
    try:
        with open(DATA_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except FileNotFoundError:
        return {}


def save_data(data: int):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


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
            "cards": []
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
    save_data(data)

    image_path = os.path.join(IMAGES_FOLDER, f"{card}.png")

    rarity_display = RARITIES.get(rarity, rarity.title())
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
                    caption = f"*{card_name}*\n\n*Rarity: {rarity_display}*\n\n{description}\n\n{link}"
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
                f"• [{card}](https://t.me/{context.bot.username}?start=collection_{card.replace(' ', '_')})"
                for card in owned_cards
            ]
            cards_text = "\n".join(cards_with_desc) if cards_with_desc else "None"
            sorted_collection.append(
                f"*{RARITIES.get(rarity, rarity.title())}* ({count_owned}/{count_total} - {percentage:.1f}%):\n{cards_text}"
            )

    global_percentage = (total_owned / total_available) * 100 if total_available > 0 else 0
    summary = f"*Total*: {total_owned}/{total_available} cards ({global_percentage:.1f}% complete)\n"

    response = str(summary + "\n\n" + "\n\n".join(sorted_collection))
    await update.message.reply_text(response, parse_mode="Markdown")



def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("card", card))
    app.add_handler(CommandHandler("collection", collection))

    print("Running the bot...")
    app.run_polling()


if __name__ == "__main__":
    main()
