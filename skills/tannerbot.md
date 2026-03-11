---
name: tannercoin
description: >
  Use this skill whenever the user wants to interact with Tannercoin games or Tannerbot on
  Telegram. Triggers include: any mention of "tannercoin", "tcoins", "tcoin", "tannerbot",
  "!mine", "!dice", "!rr", "!bj", "!horse", "!duck", "!farm", "!pokemon", "!balance",
  "!send", or any request to play games, manage currency, catch Pokemon, or run a farm
  through the Tannercoin Telegram bot. Use this skill even if the user only asks generally
  about what commands are available, how to start, or how a specific game works.
---

# Tannercoin Skill

This skill enables a chatbot to participate in Tannercoin games on Telegram by issuing
the correct commands, following game rules, and behaving like a human player (not a bot
farmer). Tannerbot lives in the [@tannercoin](http://t.me/tannercoin) Telegram group and
other chats where Tanner is present.

---

## Core Currency Commands

| Command | Description |
|---|---|
| `!balance` | Check your balance. New users start with **1000 tcoins**. |
| `!send [amount]` | Send tcoins to someone — reply to their message first. |
| `!tcoin` | View everyone's balances. |
| `!ledger` | View the full transaction ledger. |
| `!thelp` | Link to the official guide. |

---

## Mining

- `!mine` — Earn **25 tcoins**. Adds you to the front of the miner list.
  - You cannot mine again until you drop off the list.
  - Russian roulette has a slight player edge, so it also functions as a form of mining.

---

## Games

All games cost tcoins to enter. The `!allgames` command plays the next four games
automatically and has a **daily cooldown** — use it once per day.

### Quick Reference

| Command | Cost | How to Win |
|---|---|---|
| `!allgames` | Varies | Auto-plays the next 4 games (daily) |
| `!dice` | 50 tcoins | Two dice thrown — highest total wins |
| `!horse` | 50 tcoins | 6 players needed; most dice appearances wins |
| `!rr` | 30 tcoins | Russian roulette; pulling later is riskier but pays more |
| `!bj` | 40 tcoins | Blackjack; dealer bets 120, 3 players bet 40 each |
| `!tchamp` | Free | Sends 5 tcoins to a random person |
| `!duck` | 10 tcoins/attempt | First to `!bang`, `!befriend`, or `!boop` a duck wins 50 tcoins |

### Game Details

**Dice (`!dice`)**
- Two dice are thrown for each player.
- Player with the highest total wins the pot.

**Horse Race (`!horse`)**
- Requires exactly **6 players**.
- Dice are thrown repeatedly; whichever number appears most wins.
- Each player is assigned a number.

**Russian Roulette (`!rr`)**
- Players take turns pulling the trigger.
- Pulling **later** is riskier but pays out more upon survival.
- Slight player edge overall — counts as a mining alternative.

**Blackjack (`!bj`)**
- 3 players vs. 1 dealer.
- Dealer bets 120 tcoins; each player bets 40 tcoins.
- Standard blackjack rules apply.

**Duck Hunt (`!duck`)**
- Starts a hunt with **4 ducks** in the chat.
- Ducks look like: `・。。・゜゜ _ø< quack!`
- First to respond wins 50 tcoins. Each attempt costs 10 tcoins.
- Response options: `!bang` (shoot), `!befriend` (befriend), `!boop` (boop).

---

## Farm

The farm is a longer-term resource game. Start by purchasing farmland, then plant, water,
and harvest crops for passive tcoin income.

| Command | Cost | Description |
|---|---|---|
| `!farm buy` | 250 tcoins | Buy farmland to start your farm |
| `!farm view` | Free | View your farm plot |
| `!farm help` | Free | View all farm commands |
| `!farm random` | Free | Randomly place seed markers ("S") on your plot |
| `!farm edit` | Free | Get a link to manually edit your farm layout |
| `!farm reset` | Free | Clear your farm plot to blank |
| `!farm plant` | 10 tcoins/dozen | Plant seeds at each seed marker ("S") |
| `!farm water` | Free | Water your crops to keep them alive |
| `!farm harvest` | Free | Harvest mature crops ("Ŧ") for **25 tcoins each** |
| `!farm all` | Free | View everybody's farms |

### Farm Rules
- Crops only grow when water level is **"good"** or **"dry"**.
- Crops **die** after 5 days without water ("dry" for 24 hours triggers death).
- Mature crops are shown as `Ŧ` on the farm grid.
- Seed markers are shown as `S`.

---

## Pokémon

Players catch Pokémon that appear as stickers in the chat and can battle each other.

### Getting Started
- `!start charmander` / `!start bulbasaur` / `!start squirtle` — Choose a Gen I starter and receive a Pokédex.

### Core Pokémon Commands

| Command | Cost | Description |
|---|---|---|
| `!pokemon` | Free | View all Pokémon commands |
| `!pokedex` | Free | View your Pokémon and stats |
| `!pokedex [name]` | Free | View info about a specific Pokémon |
| `!pokeball` | 20 tcoins | Throw a Poké Ball to catch a Pokémon |
| `!greatball` | 60 tcoins | Throw a Great Ball (better catch rate) |
| `!ultraball` | 120 tcoins | Throw an Ultra Ball (even better) |
| `!masterball` | Free* | Throw a Master Ball (collected over time) |
| `!berry` | 30 tcoins | Make a Pokémon easier to catch |
| `!party [x] [y] [z]` | Free | Set your battle party to 3 Pokémon by name |
| `!battle` | Free | Battle someone (reply to them) |
| `!offers` | Free | View available Pokémon trades |
| `!offer [x] for [y]` | Varies | Create a trade offer; x and y can be Pokémon or tcoins |

### Jasonbot Commands
- `!suggestions [n]` — View trading pairs for trainers with `n` Pokémon.
- **Who's that Pokémon?** — Identify a Pokémon by typing its name. **Do NOT reply to the sticker** — just type the name directly.

---

## Group Photo Bidding (Tannercoin Chat only)

Available only in the [@tannercoin](http://t.me/tannercoin) group:

| Command | Description |
|---|---|
| `!pic` | View the current bid to change the group photo |
| `!pic [amount]` | Place a bid to change the group photo |

---

## Botting Guidelines

The bot **must** follow these rules to avoid being flagged as a bad actor:

1. **Always `sleep()` for at least 5 seconds** before sending any Tannerbot command.
2. **Don't play games every time** — be human-like in frequency and selection.
3. **Never bot Pokémon** — catching and battling must be done by a human.
4. **Never bot Duck Hunt** — reaction-based games must be done by a human.

---

## Workflow: How to Play

### Starting Out
1. Send `!balance` — if you get a response, you're registered. New users receive 1000 tcoins.
2. Send `!mine` to earn 25 tcoins (subject to miner list cooldown).
3. Use `!allgames` once daily to auto-participate in the next four games.

### Daily Routine (bot-safe)
1. Wait 5 seconds before each command.
2. `!mine` if not on the miner list.
3. `!allgames` once per day.
4. Optionally, `!farm water` if you own a farm.
5. Check `!balance` to track progress.

### Farming Loop
1. Buy land: `!farm buy` (250 tcoins, one-time).
2. Place seeds: `!farm random` or `!farm edit`.
3. Plant: `!farm plant`.
4. Water regularly: `!farm water` (at least every 24 hours).
5. Harvest when mature: `!farm harvest` (25 tcoins per `Ŧ` plant).

### Sending Tcoins
1. Reply to the target user's message.
2. Send: `!send [amount]`

---

## Provably Fair Games

All tcoin games are provably fair. Reference: https://telegra.ph/Tannercoin-Fairness-09-22
