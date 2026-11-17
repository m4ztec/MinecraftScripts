# Pathmind Presets

`pathmind_presets` is a dependency-free Python library for creating and validating
Pathmind preset graphs. It provides typed node, mode, parameter-name, and parameter-type
enums for editor discoverability, builders for common graph pieces, JSON-path validation
errors, and JSON loading/writing.

## Install for this workspace

From this directory, install the package in the active Python environment:

```powershell
python -m pip install -e .
```

The package requires Python 3.11 or newer and has no runtime dependencies.

## Build a preset

```python
from pathmind_presets import (
    NodeMode,
    NodeType,
    Parameter,
    ParameterName,
    ParameterType,
    Preset,
)

preset = Preset()
start = preset.add_start()
goto = preset.add_node(
    NodeType.GOTO,
    id="go_to_target",
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
preset.write("presets/test.pathmind.json")
```

GOTO uses the same `add_node` API as every other node. Set its mode and pass the mode's
parameters explicitly; the target values are absolute world coordinates, while `x` and
`y` are only the node's position on the editor canvas. The result is a regular `Node` that
can be connected normally.

Other GOTO modes have matching helpers: `add_goto_xz`, `add_goto_y`, and
`add_goto_block`. To discover supported modes for any node type, use `modes_for`:

```python
from pathmind_presets import NodeType, modes_for

print(modes_for(NodeType.GOTO))
```

For other node types, `add_node` accepts the catalog enums and `set_parameter` is
chainable:

```python
node = preset.add_node(
    NodeType.WAIT,
    id="pause",
    x=220,
    y=0,
    mode=NodeMode.WAIT_SECONDS,
)
node.set_parameter(ParameterName.DURATION, 2.5, type=ParameterType.DOUBLE)
```

Use enum members (for example `NodeType.GOTO` or `ParameterName.X`) to get Python
IntelliSense. A test checks that these vocabularies stay synchronized with the workspace
`pathmind-preset.schema.json`.

## VS Code editor feedback

Open this project folder in VS Code, install/enable the Python and Pylance extensions, and
select the workspace `.venv` interpreter with **Python: Select Interpreter**. The workspace
settings enable Pylance basic type checking. Invalid builder arguments and missing required
arguments appear as editor squiggles and in the Problems panel; completions come from the
library's enums and typed method signatures.

## Validation and loading

`Preset.validate()` returns every issue with a path such as
`nodes[1].parameters.Z.type`. `Preset.write()` and `Preset.to_json()` validate first and
raise `PresetValidationError` if anything is invalid:

```python
issues = preset.validate()
if issues:
    for issue in issues:
        print(issue)
```

Validation checks known node/mode/parameter catalog values, mode compatibility, scalar
and numeric parameter values, required GOTO parameters, unique node IDs, connection
socket values and references, and node attachment references. `Preset.from_json()` and
`Preset.from_dict()` load and validate existing presets while preserving unmodeled
Pathmind metadata.

The workspace enables Pylance basic type checking so unsupported builder arguments and
missing required arguments appear as editor diagnostics while you type. Pylance catches
Python API/type mistakes; graph-level checks such as dangling connections and required
GOTO parameters are reported by `validate()` and before `write()`.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Regenerate the villager trader preset

From this directory, run the generator as a module so it can import the local builder
library:

```powershell
python -m scripts.generate_villager_trader
```
