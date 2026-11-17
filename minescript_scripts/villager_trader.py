"""Open the nearest villager's trade screen and execute one selected offer."""

from time import sleep

from minescript import player_look_at, press_key_bind, screen_name
from minescript_plus import Screen, Trading, World


TRADE_OFFER_INDEX = 0
INTERACTION_DELAY_SECONDS = 0.1

MERCHANT_SCREEN_TITLES = {
    "Armorer",
    "Butcher",
    "Cartographer",
    "Cleric",
    "Farmer",
    "Fisherman",
    "Fletcher",
    "Leatherworker",
    "Librarian",
    "Mason",
    "Shepherd",
    "Toolsmith",
    "Villager",
    "Weaponsmith",
}


def main() -> None:
    villager = World.find_nearest_entity(type_str="villager")
    if villager is None:
        print("No villager found nearby.")
        return

    x, y, z = villager.position
    player_look_at(x, y + 1, z)
    sleep(INTERACTION_DELAY_SECONDS)

    press_key_bind("key.use", True)
    try:
        sleep(INTERACTION_DELAY_SECONDS)
    finally:
        press_key_bind("key.use", False)

    if not Screen.wait_screen():
        print("Villager trade screen did not open. Move closer and try again.")
        return

    title = screen_name()
    if title not in MERCHANT_SCREEN_TITLES:
        print(
            f"Unexpected screen {title!r}; no trade was performed. "
            "Add its title to MERCHANT_SCREEN_TITLES if this is a localized or named villager."
        )
        return

    try:
        result = Trading.get_result(TRADE_OFFER_INDEX, name_and_count=True)
        if result is None:
            print(f"Trade offer {TRADE_OFFER_INDEX} is not available.")
            return

        cost_a = Trading.get_costA(TRADE_OFFER_INDEX, name_and_count=True)
        cost_b = Trading.get_costB(TRADE_OFFER_INDEX, name_and_count=True)
        print(f"Offer {TRADE_OFFER_INDEX}: {cost_a} + {cost_b} -> {result}")

        Trading.trade_offer(TRADE_OFFER_INDEX)
        print("Trade action sent.")
    finally:
        Screen.close_screen()


main()
