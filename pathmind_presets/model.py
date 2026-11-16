"""Typed, discoverable builders for Pathmind preset JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .catalog import NodeMode, NodeType, ParameterName, ParameterType
from .validation import PresetValidationError, ValidationIssue, validate_preset

ParameterValue = str | int | float | bool


def _enum_value(value: str | NodeType | NodeMode | ParameterType | ParameterName) -> str:
    return value.value if isinstance(value, (NodeType, NodeMode, ParameterType, ParameterName)) else value


def _serialized_value(value: ParameterValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(slots=True)
class Parameter:
    """A Pathmind node parameter; values are written as strings in preset JSON."""

    name: ParameterName | str
    value: ParameterValue
    type: ParameterType | str | None = None
    id: str | None = None
    user_edited: bool | None = None

    def resolved_type(self) -> ParameterType | str:
        if self.type is not None:
            return self.type
        if isinstance(self.value, bool):
            return ParameterType.BOOLEAN
        if isinstance(self.value, int):
            return ParameterType.INTEGER
        if isinstance(self.value, float):
            return ParameterType.DOUBLE
        return ParameterType.STRING

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": _enum_value(self.name),
            "value": _serialized_value(self.value),
            "type": _enum_value(self.resolved_type()),
        }
        if self.id is not None:
            result["id"] = self.id
        if self.user_edited is not None:
            result["userEdited"] = self.user_edited
        return result


@dataclass(slots=True)
class Node:
    """A graph node with fluent parameter-setting helpers."""

    id: str
    type: NodeType | str
    x: int
    y: int
    mode: NodeMode | str | None = None
    parameters: list[Parameter] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def set_parameter(
        self,
        name: ParameterName | str,
        value: ParameterValue,
        *,
        type: ParameterType | str | None = None,
    ) -> Node:
        """Add or replace a named parameter and return this node for chaining."""
        label = _enum_value(name)
        for parameter in self.parameters:
            if _enum_value(parameter.name) == label:
                parameter.value = value
                parameter.type = type
                return self
        self.parameters.append(Parameter(name=name, value=value, type=type))
        return self

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.id,
            "type": _enum_value(self.type),
            "x": self.x,
            "y": self.y,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }
        if self.mode is not None:
            result["mode"] = _enum_value(self.mode)
        result.update(self.metadata)
        return result


@dataclass(slots=True)
class Connection:
    """A flow edge between two node sockets."""

    output_node_id: str
    input_node_id: str
    output_socket: int = 0
    input_socket: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "outputNodeId": self.output_node_id,
            "inputNodeId": self.input_node_id,
            "outputSocket": self.output_socket,
            "inputSocket": self.input_socket,
        }


@dataclass(slots=True)
class Preset:
    """A Pathmind graph that can be validated and serialized to JSON."""

    nodes: list[Node] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)
    routines: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def add_node(
        self,
        node_type: NodeType,
        *,
        id: str,
        x: int,
        y: int,
        mode: NodeMode | None = None,
        parameters: Iterable[Parameter] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> Node:
        """Add a node. Use NodeType and NodeMode enum members for autocomplete."""
        node = Node(
            id=id,
            type=node_type,
            x=x,
            y=y,
            mode=mode,
            parameters=list(parameters),
            metadata=dict(metadata or {}),
        )
        self.nodes.append(node)
        return node

    def add_start(self, *, id: str = "start", x: int = 0, y: int = 0) -> Node:
        """Add a START node."""
        return self.add_node(NodeType.START, id=id, x=x, y=y)

    def add_stop(self, *, id: str = "stop", x: int = 440, y: int = 0) -> Node:
        """Add a STOP node using Pathmind's default stop mode."""
        return self.add_node(NodeType.STOP, id=id, x=x, y=y, mode=NodeMode.STOP_NORMAL)

    def add_goto_xz(
        self,
        *,
        id: str,
        target_x: int,
        target_z: int,
        x: int = 220,
        y: int = 0,
    ) -> Node:
        """Add a GOTO node for world X/Z coordinates, letting Pathmind choose Y."""
        return self.add_node(
            NodeType.GOTO,
            id=id,
            x=x,
            y=y,
            mode=NodeMode.GOTO_XZ,
            parameters=[
                Parameter(ParameterName.X, target_x, ParameterType.INTEGER),
                Parameter(ParameterName.Z, target_z, ParameterType.INTEGER),
            ],
        )

    def add_goto_y(
        self,
        *,
        id: str,
        target_y: int,
        x: int = 220,
        y: int = 0,
    ) -> Node:
        """Add a GOTO node for an absolute world Y coordinate."""
        return self.add_node(
            NodeType.GOTO,
            id=id,
            x=x,
            y=y,
            mode=NodeMode.GOTO_Y,
            parameters=[
                Parameter(ParameterName.Y, target_y, ParameterType.INTEGER),
            ],
        )

    def add_goto_block(
        self,
        *,
        id: str,
        block: str,
        x: int = 220,
        y: int = 0,
    ) -> Node:
        """Add a GOTO node that navigates to a nearby block type."""
        return self.add_node(
            NodeType.GOTO,
            id=id,
            x=x,
            y=y,
            mode=NodeMode.GOTO_BLOCK,
            parameters=[
                Parameter(ParameterName.BLOCK, block, ParameterType.STRING),
            ],
        )

    def connect(
        self,
        output: Node | str,
        input: Node | str,
        *,
        output_socket: int = 0,
        input_socket: int = 0,
    ) -> Connection:
        """Connect two nodes by node object or id."""
        connection = Connection(
            output_node_id=output.id if isinstance(output, Node) else output,
            input_node_id=input.id if isinstance(input, Node) else input,
            output_socket=output_socket,
            input_socket=input_socket,
        )
        self.connections.append(connection)
        return connection

    def validate(self) -> tuple[ValidationIssue, ...]:
        """Return every detected problem without raising."""
        return validate_preset(self)

    def raise_if_invalid(self) -> None:
        """Raise PresetValidationError if the graph has validation issues."""
        issues = self.validate()
        if issues:
            raise PresetValidationError(issues)

    def to_dict(self, *, validate: bool = True) -> dict[str, object]:
        if validate:
            self.raise_if_invalid()
        result: dict[str, object] = {
            "nodes": [node.to_dict() for node in self.nodes],
            "connections": [connection.to_dict() for connection in self.connections],
            "routines": self.routines,
        }
        result.update(self.metadata)
        return result

    def to_json(self, *, indent: int = 2, validate: bool = True) -> str:
        return json.dumps(
            self.to_dict(validate=validate),
            indent=indent,
            ensure_ascii=False,
        )

    def write(self, path: str | Path, *, indent: int = 2) -> Path:
        """Validate and write this preset as UTF-8 JSON."""
        destination = Path(path)
        destination.write_text(self.to_json(indent=indent), encoding="utf-8")
        return destination

    @classmethod
    def read(cls, path: str | Path) -> Preset:
        """Read and validate a preset JSON file."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Preset:
        """Load a preset mapping, preserving unmodeled Pathmind metadata."""
        if not isinstance(data, Mapping):
            raise TypeError("Preset JSON root must be an object.")

        nodes_data = data.get("nodes", [])
        connections_data = data.get("connections", [])
        routines_data = data.get("routines", [])
        if not isinstance(nodes_data, list):
            raise TypeError("'nodes' must be an array.")
        if not isinstance(connections_data, list):
            raise TypeError("'connections' must be an array.")
        if not isinstance(routines_data, list) or not all(isinstance(item, dict) for item in routines_data):
            raise TypeError("'routines' must be an array of objects.")

        nodes = [_node_from_dict(item, index) for index, item in enumerate(nodes_data)]
        connections = [
            _connection_from_dict(item, index)
            for index, item in enumerate(connections_data)
        ]
        known_root_fields = {"nodes", "connections", "routines"}
        preset = cls(
            nodes=nodes,
            connections=connections,
            routines=routines_data,
            metadata={key: value for key, value in data.items() if key not in known_root_fields},
        )
        preset.raise_if_invalid()
        return preset

    @classmethod
    def from_json(cls, text: str) -> Preset:
        """Parse and validate a JSON string."""
        data = json.loads(text)
        return cls.from_dict(data)


def _node_from_dict(data: Any, index: int) -> Node:
    path = f"nodes[{index}]"
    if not isinstance(data, dict):
        raise TypeError(f"{path} must be an object.")
    parameters_data = data.get("parameters", [])
    if not isinstance(parameters_data, list):
        raise TypeError(f"{path}.parameters must be an array.")
    parameters = [
        _parameter_from_dict(parameter, f"{path}.parameters[{parameter_index}]")
        for parameter_index, parameter in enumerate(parameters_data)
    ]
    known_fields = {"id", "type", "x", "y", "mode", "parameters"}
    return Node(
        id=_require_string(data.get("id"), f"{path}.id"),
        type=_require_string(data.get("type"), f"{path}.type"),
        x=_require_integer(data.get("x"), f"{path}.x"),
        y=_require_integer(data.get("y"), f"{path}.y"),
        mode=_optional_string_field(data, "mode", path),
        parameters=parameters,
        metadata={key: value for key, value in data.items() if key not in known_fields},
    )


def _parameter_from_dict(data: Any, path: str) -> Parameter:
    if not isinstance(data, dict):
        raise TypeError(f"{path} must be an object.")
    value = data.get("value")
    if not isinstance(value, str):
        raise TypeError(f"{path}.value must be a string, as required by Pathmind preset JSON.")
    return Parameter(
        name=_require_string(data.get("name"), path + ".name"),
        value=value,
        type=_optional_string_field(data, "type", path),
        id=_optional_string_field(data, "id", path),
        user_edited=_optional_boolean_field(data, "userEdited", path),
    )


def _connection_from_dict(data: Any, index: int) -> Connection:
    path = f"connections[{index}]"
    if not isinstance(data, dict):
        raise TypeError(f"{path} must be an object.")
    return Connection(
        output_node_id=_require_string(data.get("outputNodeId"), path + ".outputNodeId"),
        input_node_id=_require_string(data.get("inputNodeId"), path + ".inputNodeId"),
        output_socket=_require_integer(data.get("outputSocket"), path + ".outputSocket"),
        input_socket=_require_integer(data.get("inputSocket"), path + ".inputSocket"),
    )


def _require_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{path} must be a string.")
    return value


def _optional_string_field(data: dict[str, object], key: str, path: str) -> str | None:
    if key not in data:
        return None
    return _require_string(data[key], f"{path}.{key}")


def _require_integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{path} must be an integer.")
    return value


def _optional_boolean_field(data: dict[str, object], key: str, path: str) -> bool | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, bool):
        raise TypeError(f"{path}.{key} must be a boolean.")
    return value
