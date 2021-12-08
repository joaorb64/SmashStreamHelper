import os
import json
import copy
from deepdiff import DeepDiff, extract
import shutil

from Helpers import deep_get, deep_set, deep_unset


class StateManager:
    state = {}

    def SaveState():
        with open("./out/program_state.json", 'w') as file:
            json.dump(StateManager.state, file, indent=4, sort_keys=True)

    def LoadState():
        with open("./out/program_state.json", 'r') as file:
            StateManager.state = json.load(file)

    def Set(key: str, value):
        oldState = copy.deepcopy(StateManager.state)
        deep_set(StateManager.state, key, value)
        StateManager.SaveState()
        StateManager.ExportText(oldState)

    def Unset(key: str):
        deep_unset(StateManager.state, key)
        StateManager.SaveState()

    def Get(key: str):
        return deep_get(StateManager.state, key)

    def ExportText(oldState):
        diff = DeepDiff(oldState, StateManager.state)
        print(diff)

        mergedDiffs = list(diff.get("values_changed", {}).items())
        mergedDiffs.extend(list(diff.get("types_changed", {}).items()))

        print(mergedDiffs)

        for changeKey, change in mergedDiffs:
            # Remove "root[" from start and separate keys
            filename = "_".join(changeKey[5:].replace(
                "'", "").replace("]", "").replace("/", "_").split("["))

            print(filename)

            if change.get("new_value").startswith("./"):
                shutil.copyfile(change.get("new_value"), f"./out/{filename}" + "." +
                                change.get("new_value").rsplit(".", 1)[-1])
            else:
                with open(f"./out/{filename}.txt", 'w') as file:
                    file.write(change.get("new_value"))


if not os.path.isfile("./out/program_state.json"):
    StateManager.SaveState()

StateManager.LoadState()
