# Minescript Scripts

## Villager trader

[villager_trader.py](./villager_trader.py) targets the nearest villager, opens its trade
screen, and submits one selected offer through the Minescript-Plus `Trading` API.

### Setup

The referenced Minescript Plus version requires Minecraft 1.21.8+, Minescript 5.0b6+,
and Python 3.10+.

1. Install Minescript Plus by placing its `minescript_plus.py` module in Minecraft's
   `minescript` directory. The script also requires installed mappings; in-game, run
   `\install_mappings` if needed.
2. Copy `villager_trader.py` into that same `minescript` directory.
3. Set `TRADE_OFFER_INDEX` in the script. It is zero-based (`0` selects the first offer).
4. Stand near the villager and run `\villager_trader` in chat.

Minescript Plus quick-moves the selected offer's result, so one invocation may complete
multiple trades if the offer and inventory allow it. The script does not loop across
villagers. If your client language or a custom-named villager produces a different trade
screen title, add that title to `MERCHANT_SCREEN_TITLES`.