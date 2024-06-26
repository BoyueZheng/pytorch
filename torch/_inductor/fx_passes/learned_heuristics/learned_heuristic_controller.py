import importlib
import inspect
import pkgutil

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from torch._inductor.autoheuristic_utils import Choice, ContextDictT
from torch._inductor.fx_passes.learned_heuristics.learnedheuristic_interface import (
    LearnedHeuristic,
)


def find_and_instantiate_subclasses(
    package_name: str, base_class: Any
) -> List[LearnedHeuristic]:
    instances = []

    package = importlib.import_module(package_name)
    for _, module_name, _ in pkgutil.walk_packages(
        package.__path__, package.__name__ + "."
    ):
        try:
            module_basename = module_name.split(".")[-1]
            if not module_basename.startswith("_"):
                # learned heuristics start with an underscore
                continue
            module = importlib.import_module(module_name)

            # look for classes that are subclasses of base_class
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, base_class)
                    and obj != base_class
                ):
                    instance = obj()
                    instances.append(instance)
        except Exception as e:
            print(f"Error processing module {module_name}: {e}")

    return instances


class LearnedHeuristicController:
    existing_heuristics: Dict[str, List[LearnedHeuristic]] = defaultdict(list)
    heuristics_initialized: bool = False

    def __init__(
        self,
        name: str,
        context_dict: ContextDictT,
        choices: List[Choice],
        shared_memory: Any,
        device_capa: Tuple[int, int],
    ) -> None:
        self.name = name
        self.context_dict = context_dict
        self.choices = choices
        self.shared_memory = shared_memory
        self.device_capa = device_capa

    def get_heuristics(self, name: str) -> List[LearnedHeuristic]:
        if not LearnedHeuristicController.heuristics_initialized:
            # learned heuristics are generated into the following package
            learned_heuristics_package = "torch._inductor.fx_passes.learned_heuristics"

            # learned heuristics have to be of type LearnedHeuristic
            base_class = LearnedHeuristic
            found_heuristics = find_and_instantiate_subclasses(
                learned_heuristics_package, base_class
            )

            for learned_heuristic in found_heuristics:
                opt_name = learned_heuristic.get_name()
                LearnedHeuristicController.existing_heuristics[opt_name].append(
                    learned_heuristic
                )
            LearnedHeuristicController.heuristics_initialized = True

        return LearnedHeuristicController.existing_heuristics[name]

    def get_decision(self) -> Optional[Choice]:
        heuristics = self.get_heuristics(self.name)
        for heuristic in heuristics:
            if heuristic.check_precondition(
                self.name, self.context_dict, self.shared_memory, self.device_capa
            ):
                return heuristic.get_decision(self.context_dict, self.choices)
        return None
