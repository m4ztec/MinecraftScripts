import json
import tempfile
import unittest
from pathlib import Path

from pathmind_presets import (
    NodeMode,
    NodeType,
    Parameter,
    ParameterName,
    ParameterType,
    Preset,
    PresetValidationError,
    modes_for,
)


ROOT = Path(__file__).resolve().parents[1]


class PresetBuilderTests(unittest.TestCase):
    def build_test_graph(self) -> Preset:
        preset = Preset()
        start = preset.add_start()
        goto = preset.add_node(
            NodeType.GOTO,
            id="move_left_1",
            x=220,
            y=0,
            mode=NodeMode.GOTO_XYZ,
            parameters=[
                Parameter(ParameterName.X, -1, ParameterType.INTEGER),
                Parameter(ParameterName.Y, 64, ParameterType.INTEGER),
                Parameter(ParameterName.Z, 0, ParameterType.INTEGER),
            ],
        )
        stop = preset.add_stop()
        preset.connect(start, goto)
        preset.connect(goto, stop)
        return preset

    def test_builder_matches_current_test_preset(self) -> None:
        expected = json.loads((ROOT / "presets" / "test.pathmind.json").read_text(encoding="utf-8"))
        self.assertEqual(self.build_test_graph().to_dict(), expected)

    def test_generic_node_builder_sets_goto_mode_and_parameter_types(self) -> None:
        preset = self.build_test_graph()
        goto = preset.nodes[1]
        self.assertEqual(goto.type, NodeType.GOTO)
        self.assertEqual(goto.mode, NodeMode.GOTO_XYZ)
        self.assertEqual([parameter.name for parameter in goto.parameters], [
            ParameterName.X,
            ParameterName.Y,
            ParameterName.Z,
        ])
        self.assertTrue(all(parameter.type is ParameterType.INTEGER for parameter in goto.parameters))

    def test_all_goto_helpers_and_catalog_modes_validate(self) -> None:
        preset = Preset()
        preset.add_goto_xz(id="xz", target_x=-1, target_z=0)
        preset.add_goto_y(id="y", target_y=64)
        preset.add_goto_block(id="block", block="minecraft:stone")
        self.assertEqual(preset.validate(), ())
        self.assertEqual(
            {mode.value for mode in modes_for(NodeType.GOTO)},
            {"GOTO_XYZ", "GOTO_XZ", "GOTO_Y", "GOTO_BLOCK"},
        )

    def test_goto_requires_all_coordinates(self) -> None:
        preset = self.build_test_graph()
        preset.nodes[1].parameters.pop()
        issues = preset.validate()
        self.assertTrue(any("missing 'Z' parameter" in issue.message for issue in issues))
        with self.assertRaises(PresetValidationError):
            preset.to_json()

    def test_goto_rejects_non_integer_coordinate_text(self) -> None:
        preset = self.build_test_graph()
        preset.nodes[1].parameters[0].value = "one"
        issues = preset.validate()
        self.assertTrue(any("must be an integer" in issue.message for issue in issues))

    def test_invalid_mode_and_dangling_connection_are_reported(self) -> None:
        preset = self.build_test_graph()
        preset.nodes[1].mode = NodeMode.WAIT_SECONDS
        preset.connect("missing", "stop")
        issues = preset.validate()
        self.assertTrue(any(issue.path == "nodes[1].mode" for issue in issues))
        self.assertTrue(any(issue.path == "connections[2].outputNodeId" for issue in issues))

    def test_duplicate_node_ids_are_reported(self) -> None:
        preset = self.build_test_graph()
        preset.add_node(NodeType.START, id="start", x=0, y=100)
        self.assertTrue(any("duplicate node id" in issue.message for issue in preset.validate()))

    def test_attachment_can_reference_a_node_that_appears_later(self) -> None:
        preset = Preset()
        preset.add_node(
            NodeType.SENSOR_TOUCHING_BLOCK,
            id="host",
            x=0,
            y=0,
            metadata={"attachedSensorId": "sensor"},
        )
        preset.add_node(NodeType.PARAM_BLOCK, id="sensor", x=0, y=100)
        self.assertEqual(preset.validate(), ())

    def test_non_string_parameter_values_are_rejected_when_loading_json(self) -> None:
        data = self.build_test_graph().to_dict()
        nodes = data["nodes"]
        if not isinstance(nodes, list):
            self.fail("'nodes' should be an array")
        node = nodes[1]
        if not isinstance(node, dict):
            self.fail("node should be an object")
        parameters = node["parameters"]
        if not isinstance(parameters, list):
            self.fail("'parameters' should be an array")
        parameter = parameters[0]
        if not isinstance(parameter, dict):
            self.fail("parameter should be an object")
        parameter["value"] = -1
        with self.assertRaisesRegex(TypeError, r"value must be a string"):
            Preset.from_dict(data)

    def test_from_json_validates_and_preserves_existing_preset(self) -> None:
        source = (ROOT / "presets" / "test.pathmind.json").read_text(encoding="utf-8")
        loaded = Preset.from_json(source)
        self.assertEqual(loaded.to_dict(), json.loads(source))

    def test_write_creates_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "generated.pathmind.json"
            self.build_test_graph().write(path)
            self.assertEqual(Preset.from_json(path.read_text(encoding="utf-8")).to_dict(),
                             self.build_test_graph().to_dict())

    def test_catalog_matches_editor_schema(self) -> None:
        schema = json.loads((ROOT / "pathmind-preset.schema.json").read_text(encoding="utf-8"))
        definitions = schema["definitions"]
        self.assertEqual(
            [item.value for item in NodeType],
            definitions["node"]["properties"]["type"]["enum"],
        )
        self.assertEqual(
            [item.value for item in NodeMode],
            definitions["node"]["properties"]["mode"]["enum"],
        )
        self.assertEqual(
            [item.value for item in ParameterType],
            definitions["parameter"]["properties"]["type"]["enum"],
        )
        self.assertEqual(
            [item.value for item in ParameterName],
            definitions["parameter"]["properties"]["name"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
