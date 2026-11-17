from pathlib import Path

from pathmind_presets import (
    NodeMode,
    NodeType,
    Parameter,
    ParameterName,
    ParameterType,
    Preset,
)


# Set this to the 1-based Mason offer number that buys stone in your trade menu.
STONE_TRADE_NUMBER = 3
MAX_TRADES_PER_VILLAGER = 64

preset = Preset()
start = preset.add_start()


def add_relative_direction(node_id: str, yaw_offset: str, *, x: int):
    return preset.add_node(
        NodeType.PARAM_DIRECTION,
        id=node_id,
        x=x,
        y=140,
        parameters=[
            Parameter(ParameterName.MODE, "exact", ParameterType.STRING),
            Parameter(ParameterName.YAW, yaw_offset, ParameterType.STRING),
            Parameter(ParameterName.PITCH, "~0", ParameterType.STRING),
        ],
    )


def add_villager_target(node_id: str, *, x: int):
    return preset.add_node(
        NodeType.PARAM_ENTITY,
        id=node_id,
        x=x,
        y=140,
        parameters=[
            Parameter(ParameterName.ENTITY, "minecraft:villager", ParameterType.STRING),
        ],
    )


def add_walk(
    node_id: str,
    direction_id: str,
    yaw_offset: str,
    *,
    distance: float,
    x: int,
):
    direction = add_relative_direction(direction_id, yaw_offset, x=x)
    return preset.add_node(
        NodeType.WALK,
        id=node_id,
        x=x,
        y=0,
        mode=NodeMode.WALK_FOR,
        parameters=[
            Parameter(ParameterName.DURATION, 30.0, ParameterType.DOUBLE),
            Parameter(ParameterName.DISTANCE, distance, ParameterType.DOUBLE),
        ],
        metadata={
            "parameterAttachments": [
                {"slotIndex": 0, "parameterNodeId": direction.id},
            ],
        },
    )


def add_interaction(node_id: str, target_id: str, *, x: int):
    target = add_villager_target(target_id, x=x)
    return preset.add_node(
        NodeType.INTERACT,
        id=node_id,
        x=x,
        y=0,
        metadata={
            "parameterAttachments": [
                {"slotIndex": 0, "parameterNodeId": target.id},
            ],
        },
    )


def add_wait(node_id: str, *, x: int):
    return preset.add_node(
        NodeType.WAIT,
        id=node_id,
        x=x,
        y=0,
        mode=NodeMode.WAIT_SECONDS,
        parameters=[Parameter(ParameterName.DURATION, 1.0, ParameterType.DOUBLE)],
    )


def add_trade(node_id: str, *, x: int):
    return preset.add_node(
        NodeType.TRADE,
        id=node_id,
        x=x,
        y=0,
        parameters=[
            Parameter(ParameterName.NUMBER, STONE_TRADE_NUMBER, ParameterType.INTEGER),
            Parameter(ParameterName.COUNT, MAX_TRADES_PER_VILLAGER, ParameterType.INTEGER),
        ],
    )


def add_close_trade_screen(node_id: str, *, x: int):
    return preset.add_node(
        NodeType.CLOSE_GUI,
        id=node_id,
        x=x,
        y=0,
        mode=NodeMode.PLAYER_GUI_CLOSE,
    )


approach_first = add_walk(
    "approach_first",
    "approach_direction",
    "~0",
    distance=2.0,
    x=220,
)
interact_first = add_interaction("interact_first", "first_villager", x=440)
wait_first = add_wait("wait_for_first_trade_screen", x=660)
trade_first = add_trade("trade_with_first_villager", x=880)
close_first = add_close_trade_screen("close_first_trade_screen", x=1100)

move_left = add_walk(
    "move_left_to_next",
    "left_direction",
    "~-90",
    distance=2.0,
    x=1320,
)
interact_next = add_interaction("interact_next", "next_villager", x=1540)
wait_next = add_wait("wait_for_next_trade_screen", x=1760)
trade_next = add_trade("trade_with_next_villager", x=1980)
close_next = add_close_trade_screen("close_next_trade_screen", x=2200)
stop = preset.add_stop(x=2420)

for current, following in (
    (start, approach_first),
    (approach_first, interact_first),
    (interact_first, wait_first),
    (wait_first, trade_first),
    (trade_first, close_first),
    (close_first, move_left),
    (move_left, interact_next),
    (interact_next, wait_next),
    (wait_next, trade_next),
    (trade_next, close_next),
    (close_next, stop),
):
    preset.connect(current, following)

preset.write(Path(__file__).resolve().parents[1] / "presets" / "villager_trader.pathmind.json")
