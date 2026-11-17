"""Semantic validation for Pathmind preset graphs."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .catalog import NodeMode, NodeType, ParameterName, ParameterType

if TYPE_CHECKING:
    from .model import Node, Parameter, Preset


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation problem with its location in the preset JSON."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class PresetValidationError(ValueError):
    """Raised when a preset cannot be serialized safely."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        details = "\n".join(f"- {issue}" for issue in issues)
        super().__init__(f"Preset validation failed:\n{details}")


NODE_MODES: dict[NodeType, frozenset[NodeMode]] = {
    NodeType.CLICK_SLOT: frozenset(
        {
            NodeMode.CLICK_SLOT_LEFT,
            NodeMode.CLICK_SLOT_RIGHT,
            NodeMode.CLICK_SLOT_SHIFT,
            NodeMode.CLICK_SLOT_SWAP_OFFHAND,
        }
    ),
    NodeType.WALK: frozenset({NodeMode.WALK_FOR, NodeMode.WALK_UNTIL}),
    NodeType.GOTO: frozenset(
        {NodeMode.GOTO_XYZ, NodeMode.GOTO_XZ, NodeMode.GOTO_Y, NodeMode.GOTO_BLOCK}
    ),
    NodeType.TRAVEL: frozenset(
        {NodeMode.GOTO_XYZ, NodeMode.GOTO_XZ, NodeMode.GOTO_Y, NodeMode.GOTO_BLOCK}
    ),
    NodeType.GOAL: frozenset(
        {
            NodeMode.GOAL_XYZ,
            NodeMode.GOAL_XZ,
            NodeMode.GOAL_Y,
            NodeMode.GOAL_CURRENT,
            NodeMode.GOAL_CLEAR,
        }
    ),
    NodeType.COLLECT: frozenset({NodeMode.COLLECT_SINGLE, NodeMode.COLLECT_MULTIPLE}),
    NodeType.BUILD: frozenset({NodeMode.BUILD_PLAYER, NodeMode.BUILD_XYZ}),
    NodeType.EXPLORE: frozenset(
        {NodeMode.EXPLORE_CURRENT, NodeMode.EXPLORE_XYZ, NodeMode.EXPLORE_FILTER}
    ),
    NodeType.FOLLOW: frozenset(
        {
            NodeMode.FOLLOW_PLAYER,
            NodeMode.FOLLOW_PLAYERS,
            NodeMode.FOLLOW_ENTITIES,
            NodeMode.FOLLOW_ENTITY_TYPE,
        }
    ),
    NodeType.CRAFT: frozenset(
        {NodeMode.CRAFT_PLAYER_GUI, NodeMode.CRAFT_CRAFTING_TABLE}
    ),
    NodeType.OPEN_INVENTORY: frozenset({NodeMode.PLAYER_GUI_OPEN}),
    NodeType.CLOSE_GUI: frozenset({NodeMode.PLAYER_GUI_CLOSE}),
    NodeType.UI_UTILS: frozenset(
        {
            NodeMode.UI_UTILS_CLOSE_WITHOUT_PACKET,
            NodeMode.UI_UTILS_CLOSE_SIGN_WITHOUT_PACKET,
            NodeMode.UI_UTILS_DESYNC,
            NodeMode.UI_UTILS_ENABLE_DELAY_PACKETS,
            NodeMode.UI_UTILS_FLUSH_DELAYED_PACKETS,
            NodeMode.UI_UTILS_SAVE_GUI,
            NodeMode.UI_UTILS_RESTORE_GUI,
            NodeMode.UI_UTILS_DISCONNECT,
            NodeMode.UI_UTILS_DISCONNECT_AND_SEND,
            NodeMode.UI_UTILS_COPY_TITLE_JSON,
            NodeMode.UI_UTILS_FABRICATE_CLICK_SLOT,
            NodeMode.UI_UTILS_FABRICATE_BUTTON_CLICK,
            NodeMode.UI_UTILS_SET_ENABLED,
            NodeMode.UI_UTILS_SET_BYPASS_RESOURCE_PACK,
            NodeMode.UI_UTILS_SET_FORCE_DENY_RESOURCE_PACK,
        }
    ),
    NodeType.FARM: frozenset({NodeMode.FARM_RANGE, NodeMode.FARM_WAYPOINT}),
    NodeType.STOP: frozenset(
        {NodeMode.STOP_NORMAL, NodeMode.STOP_CANCEL, NodeMode.STOP_FORCE}
    ),
    NodeType.WAIT: frozenset(
        {
            NodeMode.WAIT_SECONDS,
            NodeMode.WAIT_TICKS,
            NodeMode.WAIT_MINUTES,
            NodeMode.WAIT_HOURS,
        }
    ),
    NodeType.PARAM_DURATION: frozenset(
        {
            NodeMode.WAIT_SECONDS,
            NodeMode.WAIT_TICKS,
            NodeMode.WAIT_MINUTES,
            NodeMode.WAIT_HOURS,
        }
    ),
    NodeType.SENSOR_POSITION_OF: frozenset(
        {
            NodeMode.SENSOR_POSITION_X,
            NodeMode.SENSOR_POSITION_Y,
            NodeMode.SENSOR_POSITION_Z,
            NodeMode.SENSOR_POSITION_XYZ,
        }
    ),
    NodeType.SENSOR_LOOK_DIRECTION: frozenset(
        {
            NodeMode.SENSOR_LOOK_YAW,
            NodeMode.SENSOR_LOOK_PITCH,
            NodeMode.SENSOR_LOOK_ROTATION,
        }
    ),
}

_GOTO_PARAMETERS: dict[NodeMode, tuple[tuple[str, ParameterType], ...]] = {
    NodeMode.GOTO_XYZ: (
        ("X", ParameterType.INTEGER),
        ("Y", ParameterType.INTEGER),
        ("Z", ParameterType.INTEGER),
    ),
    NodeMode.GOTO_XZ: (
        ("X", ParameterType.INTEGER),
        ("Z", ParameterType.INTEGER),
    ),
    NodeMode.GOTO_Y: (("Y", ParameterType.INTEGER),),
    NodeMode.GOTO_BLOCK: (("Block", ParameterType.STRING),),
}

_NODE_REFERENCE_FIELDS = (
    "attachedSensorId",
    "parentControlId",
    "attachedActionId",
    "parentActionControlId",
    "attachedParameterId",
    "parentParameterHostId",
    "runtimeSourceNodeId",
)
_NODE_STRING_FIELDS = (
    "routineId",
    "routineInputId",
    "templateName",
    "bookText",
    "stickyNoteText",
)
_NODE_INTEGER_FIELDS = (
    "parameterSlotCount",
    "startNodeNumber",
    "stickyNoteWidth",
    "stickyNoteHeight",
    "templateVersion",
)
_NODE_BOOLEAN_FIELDS = (
    "booleanToggleValue",
    "messageClientSide",
    "gotoAllowBreakWhileExecuting",
    "gotoAllowPlaceWhileExecuting",
    "keyPressedActivatesInGuis",
)
_NODE_ENUM_FIELDS = {
    "startLaunchMode": {
        "manual",
        "client_launch",
        "world_join",
        "main_menu_open",
        "screen_opened",
    },
    "startScreenTarget": {
        "any",
        "main_menu",
        "pause_menu",
        "chat",
        "inventory",
        "merchant",
        "visual_editor",
    },
    "runtimeValueScope": {"CHAIN", "GLOBAL"},
}


def validate_preset(preset: Preset) -> tuple[ValidationIssue, ...]:
    """Check catalog values, parameter values, ids, and graph references."""
    from .model import Connection, Node, Parameter

    issues: list[ValidationIssue] = []
    node_ids: set[str] = set()
    parameter_names = {item.value for item in ParameterName}

    if not isinstance(preset.nodes, list):
        return (ValidationIssue("nodes", "must be an array of Node objects"),)
    if not isinstance(preset.connections, list):
        return (ValidationIssue("connections", "must be an array of Connection objects"),)

    for index, node in enumerate(preset.nodes):
        if not isinstance(node, Node) or not isinstance(node.id, str) or not node.id.strip():
            continue
        if node.id in node_ids:
            issues.append(
                ValidationIssue(f"nodes[{index}].id", f"duplicate node id {node.id!r}")
            )
        else:
            node_ids.add(node.id)

    for index, node in enumerate(preset.nodes):
        path = f"nodes[{index}]"
        if not isinstance(node, Node):
            issues.append(ValidationIssue(path, "must be a Node"))
            continue

        if not isinstance(node.id, str) or not node.id.strip():
            issues.append(ValidationIssue(f"{path}.id", "must be a non-empty string"))

        try:
            node_type = NodeType(node.type)
        except (ValueError, TypeError):
            issues.append(ValidationIssue(f"{path}.type", f"unknown node type {node.type!r}"))
            node_type = None

        _validate_coordinate(node.x, f"{path}.x", issues)
        _validate_coordinate(node.y, f"{path}.y", issues)

        selected_mode: NodeMode | None = None
        if node.mode is not None:
            try:
                selected_mode = NodeMode(node.mode)
            except (ValueError, TypeError):
                issues.append(ValidationIssue(f"{path}.mode", f"unknown mode {node.mode!r}"))
            else:
                allowed_modes = NODE_MODES.get(node_type) if node_type is not None else None
                if allowed_modes is None or selected_mode not in allowed_modes:
                    issues.append(
                        ValidationIssue(
                            f"{path}.mode",
                            f"{selected_mode.value} is not a mode for {node_type.value if node_type else node.type}",
                        )
                    )

        if not isinstance(node.parameters, list):
            issues.append(ValidationIssue(f"{path}.parameters", "must be an array"))
            parameters_by_name: dict[str, Parameter] = {}
        else:
            seen_parameter_names: set[str] = set()
            parameters_by_name = {}
            for parameter_index, parameter in enumerate(node.parameters):
                parameter_path = f"{path}.parameters[{parameter_index}]"
                if not isinstance(parameter, Parameter):
                    issues.append(ValidationIssue(parameter_path, "must be a Parameter"))
                    continue
                name = _as_enum_value(parameter.name)
                if (
                    not isinstance(name, str)
                    or (name not in parameter_names and node_type is not NodeType.ROUTINE_CALL)
                ):
                    issues.append(
                        ValidationIssue(
                            parameter_path + ".name",
                            f"unknown parameter label {name!r}",
                        )
                    )
                    continue
                if name in seen_parameter_names:
                    issues.append(
                        ValidationIssue(parameter_path + ".name", f"duplicate parameter {name!r}")
                    )
                seen_parameter_names.add(name)
                parameters_by_name[name] = parameter
                _validate_parameter(parameter, parameter_path, issues)

        effective_mode = selected_mode
        if effective_mode is None and node_type in {NodeType.GOTO, NodeType.TRAVEL}:
            effective_mode = NodeMode.GOTO_XYZ
        if effective_mode in _GOTO_PARAMETERS:
            _validate_goto_parameters(
                parameters_by_name,
                _GOTO_PARAMETERS[effective_mode],
                path,
                issues,
            )

        _validate_node_metadata(node, path, node_ids, issues)

    for index, connection in enumerate(preset.connections):
        path = f"connections[{index}]"
        if not isinstance(connection, Connection):
            issues.append(ValidationIssue(path, "must be a Connection"))
            continue
        for field_name, node_id in (
            ("outputNodeId", connection.output_node_id),
            ("inputNodeId", connection.input_node_id),
        ):
            if not isinstance(node_id, str) or not node_id:
                issues.append(ValidationIssue(f"{path}.{field_name}", "must be a non-empty string"))
            elif node_id not in node_ids:
                issues.append(ValidationIssue(f"{path}.{field_name}", f"unknown node id {node_id!r}"))
        _validate_socket(connection.output_socket, f"{path}.outputSocket", issues)
        _validate_socket(connection.input_socket, f"{path}.inputSocket", issues)

    if not isinstance(preset.routines, list):
        issues.append(ValidationIssue("routines", "must be an array"))
    else:
        for index, routine in enumerate(preset.routines):
            if not isinstance(routine, dict):
                issues.append(ValidationIssue(f"routines[{index}]", "must be an object"))
            else:
                _validate_routine(routine, f"routines[{index}]", issues)
                if "graph" in routine:
                    _validate_embedded_graph(
                        routine["graph"],
                        f"routines[{index}].graph",
                        issues,
                    )

    if not isinstance(preset.metadata, dict):
        issues.append(ValidationIssue("", "preset metadata must be an object"))
        root_metadata: dict[str, object] = {}
    else:
        root_metadata = preset.metadata

    if "customNodeDefinition" in root_metadata:
        _validate_custom_node_definition(
            root_metadata["customNodeDefinition"],
            "customNodeDefinition",
            issues,
        )

    reserved_root_fields = {"nodes", "connections", "routines"}
    for key in reserved_root_fields.intersection(root_metadata):
        issues.append(ValidationIssue(key, "cannot be overridden through preset metadata"))
    return tuple(issues)


def _validate_coordinate(value: object, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        issues.append(ValidationIssue(path, "must be an integer"))


def _validate_socket(value: object, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        issues.append(ValidationIssue(path, "must be a non-negative integer"))


def _validate_parameter(
    parameter: Parameter,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    value = parameter.value
    if not isinstance(value, (str, int, float, bool)):
        issues.append(
            ValidationIssue(path + ".value", "must be a string, integer, float, or boolean")
        )
        return
    if isinstance(value, float) and not math.isfinite(value):
        issues.append(ValidationIssue(path + ".value", "must be finite"))
    if parameter.id is not None and not isinstance(parameter.id, str):
        issues.append(ValidationIssue(path + ".id", "must be a string"))
    if parameter.user_edited is not None and not isinstance(parameter.user_edited, bool):
        issues.append(ValidationIssue(path + ".userEdited", "must be a boolean"))

    try:
        parameter_type = ParameterType(parameter.resolved_type())
    except (ValueError, TypeError):
        issues.append(
            ValidationIssue(path + ".type", f"unknown parameter type {parameter.resolved_type()!r}")
        )
        return

    if parameter_type is ParameterType.INTEGER:
        if isinstance(value, bool):
            valid = False
        else:
            valid = re.fullmatch(r"[+-]?\d+", str(value)) is not None
        if not valid:
            issues.append(ValidationIssue(path + ".value", "must be an integer for INTEGER parameters"))
    elif parameter_type is ParameterType.DOUBLE:
        try:
            valid = math.isfinite(float(value)) and not isinstance(value, bool)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            issues.append(ValidationIssue(path + ".value", "must be a finite number for DOUBLE parameters"))
    elif parameter_type is ParameterType.BOOLEAN:
        valid = isinstance(value, bool) or (
            isinstance(value, str) and value.lower() in {"true", "false"}
        )
        if not valid:
            issues.append(ValidationIssue(path + ".value", "must be true or false for BOOLEAN parameters"))


def _validate_goto_parameters(
    parameters: dict[str, Parameter],
    required: tuple[tuple[str, ParameterType], ...],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    for name, expected_type in required:
        parameter = parameters.get(name)
        if parameter is None:
            issues.append(
                ValidationIssue(
                    f"{path}.parameters",
                    f"missing {name!r} parameter required by this GOTO mode",
                )
            )
            continue
        try:
            actual_type = ParameterType(parameter.resolved_type())
        except (ValueError, TypeError):
            continue
        if actual_type is not expected_type:
            issues.append(
                ValidationIssue(
                    f"{path}.parameters.{name}.type",
                    f"must be {expected_type.value} for this GOTO mode",
                )
            )


def _validate_node_metadata(
    node: Node,
    path: str,
    node_ids: set[str],
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(node.metadata, dict):
        issues.append(ValidationIssue(path, "metadata must be an object"))
        return
    reserved = {"id", "type", "x", "y", "mode", "parameters"}
    for key in reserved.intersection(node.metadata):
        issues.append(ValidationIssue(f"{path}.{key}", "cannot be overridden through node metadata"))

    for field in _NODE_REFERENCE_FIELDS:
        if field not in node.metadata:
            continue
        reference = node.metadata.get(field)
        if not isinstance(reference, str):
            issues.append(ValidationIssue(f"{path}.{field}", "must be a string"))
        elif reference and reference not in node_ids:
            issues.append(
                ValidationIssue(f"{path}.{field}", f"unknown node id {reference!r}")
            )

    for field in _NODE_STRING_FIELDS:
        _validate_optional_type(node.metadata, field, str, path, issues)
    for field in _NODE_INTEGER_FIELDS:
        _validate_optional_type(node.metadata, field, int, path, issues)
    for field in _NODE_BOOLEAN_FIELDS:
        _validate_optional_type(node.metadata, field, bool, path, issues)
    for field, allowed_values in _NODE_ENUM_FIELDS.items():
        value = node.metadata.get(field)
        if field in node.metadata and (
            not isinstance(value, str) or value not in allowed_values
        ):
            issues.append(
                ValidationIssue(
                    f"{path}.{field}",
                    f"must be one of {', '.join(sorted(allowed_values))}",
                )
            )
    message_lines = node.metadata.get("messageLines")
    if "messageLines" in node.metadata and (
        not isinstance(message_lines, list)
        or not all(isinstance(line, str) for line in message_lines)
    ):
        issues.append(ValidationIssue(f"{path}.messageLines", "must be an array of strings"))

    attachments = node.metadata.get("parameterAttachments", [])
    if not isinstance(attachments, list):
        issues.append(ValidationIssue(f"{path}.parameterAttachments", "must be an array"))
    else:
        for index, attachment in enumerate(attachments):
            attachment_path = f"{path}.parameterAttachments[{index}]"
            if not isinstance(attachment, dict):
                issues.append(ValidationIssue(attachment_path, "must be an object"))
                continue
            slot = attachment.get("slotIndex")
            if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
                issues.append(
                    ValidationIssue(attachment_path + ".slotIndex", "must be a non-negative integer")
                )
            parameter_node_id = attachment.get("parameterNodeId")
            if not isinstance(parameter_node_id, str) or parameter_node_id not in node_ids:
                issues.append(
                    ValidationIssue(
                        attachment_path + ".parameterNodeId",
                        f"unknown node id {parameter_node_id!r}",
                    )
                )
            if "routineInputId" in attachment and not isinstance(
                attachment["routineInputId"], str
            ):
                issues.append(
                    ValidationIssue(
                        attachment_path + ".routineInputId",
                        "must be a string",
                    )
                )

    arguments = node.metadata.get("routineArguments")
    if "routineArguments" in node.metadata:
        if not isinstance(arguments, list):
            issues.append(ValidationIssue(f"{path}.routineArguments", "must be an array"))
        else:
            for index, argument in enumerate(arguments):
                _validate_routine_argument(
                    argument,
                    f"{path}.routineArguments[{index}]",
                    issues,
                )

    if "templateGraph" in node.metadata:
        _validate_embedded_graph(
            node.metadata["templateGraph"],
            f"{path}.templateGraph",
            issues,
        )


def _validate_optional_type(
    values: dict[str, object],
    key: str,
    expected_type: type[object],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if key not in values:
        return
    value = values[key]
    valid = isinstance(value, expected_type)
    if expected_type is int and isinstance(value, bool):
        valid = False
    if not valid:
        issues.append(
            ValidationIssue(f"{path}.{key}", f"must be {expected_type.__name__}")
        )


def _validate_routine(
    routine: dict[str, object],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    for field in (
        "id",
        "name",
        "interfaceSignature",
        "implementationSignature",
        "libraryRoutineId",
    ):
        _validate_optional_type(routine, field, str, path, issues)
    for field in ("interfaceVersion", "implementationRevision"):
        _validate_optional_type(routine, field, int, path, issues)

    if "inputs" in routine:
        inputs = routine["inputs"]
        if not isinstance(inputs, list):
            issues.append(ValidationIssue(f"{path}.inputs", "must be an array"))
        else:
            for index, routine_input in enumerate(inputs):
                _validate_routine_input(
                    routine_input,
                    f"{path}.inputs[{index}]",
                    issues,
                )


def _validate_routine_input(
    routine_input: object,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(routine_input, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    for field in ("id", "label", "valueKind", "defaultValue"):
        _validate_optional_type(routine_input, field, str, path, issues)
    _validate_optional_type(routine_input, "required", bool, path, issues)
    _validate_optional_type(routine_input, "order", int, path, issues)
    traits = routine_input.get("acceptedTraits")
    if "acceptedTraits" in routine_input and (
        not isinstance(traits, list)
        or not all(isinstance(trait, str) for trait in traits)
    ):
        issues.append(ValidationIssue(f"{path}.acceptedTraits", "must be an array of strings"))


def _validate_routine_argument(
    argument: object,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(argument, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    for field in ("inputId", "label", "valueKind", "defaultValue"):
        _validate_optional_type(argument, field, str, path, issues)
    _validate_optional_type(argument, "required", bool, path, issues)
    _validate_optional_type(argument, "orphaned", bool, path, issues)


def _validate_custom_node_definition(
    definition: object,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(definition, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    for field in ("presetName", "name", "signature"):
        _validate_optional_type(definition, field, str, path, issues)
    _validate_optional_type(definition, "version", int, path, issues)
    for field in ("inputs", "outputs"):
        if field not in definition:
            continue
        ports = definition[field]
        if not isinstance(ports, list):
            issues.append(ValidationIssue(f"{path}.{field}", "must be an array"))
            continue
        for index, port in enumerate(ports):
            port_path = f"{path}.{field}[{index}]"
            if not isinstance(port, dict):
                issues.append(ValidationIssue(port_path, "must be an object"))
                continue
            for port_field in ("name", "type", "defaultValue"):
                _validate_optional_type(port, port_field, str, port_path, issues)


def _validate_embedded_graph(
    graph: object,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if graph is None:
        return
    if not isinstance(graph, dict):
        issues.append(ValidationIssue(path, "must be an object"))
        return
    from .model import Preset

    try:
        Preset.from_dict(graph)
    except PresetValidationError as error:
        issues.extend(
            ValidationIssue(f"{path}.{issue.path}", issue.message)
            for issue in error.issues
        )
    except (TypeError, ValueError) as error:
        issues.append(ValidationIssue(path, str(error)))


def _as_enum_value(value: object) -> object:
    return getattr(value, "value", value)


def modes_for(node_type: NodeType | str) -> tuple[NodeMode, ...]:
    """Return modes supported by a node type in Pathmind's node catalog."""
    try:
        resolved_type = NodeType(node_type)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Unknown Pathmind node type: {node_type!r}") from error
    supported = NODE_MODES.get(resolved_type, frozenset())
    return tuple(mode for mode in NodeMode if mode in supported)
