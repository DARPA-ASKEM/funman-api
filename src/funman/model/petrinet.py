from typing import Dict, List, Union

import graphviz
from pydantic import BaseModel

from funman.representation.representation import Parameter
from funman.translate.petrinet import PetrinetEncoder

from .model import Model


class PetrinetDynamics(BaseModel):
    json_graph: Dict[str, List[Dict[str, Union[int, str, Dict[str, str]]]]]

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)
    #     self.json_graph = kwargs["json_graph"]
    #     self._initialize_from_json()


class PetrinetModel(Model):
    petrinet: PetrinetDynamics

    def default_encoder(self, config: "FUNMANConfig") -> "Encoder":
        """
        Return the default Encoder for the model

        Returns
        -------
        Encoder
            SMT encoder for model
        """
        return PetrinetEncoder(
            config=config,
            model=self,
        )

    def _state_vars(self):
        return self.petrinet.json_graph["S"]

    def _state_var_names(self):
        return [s["sname"] for s in self.petrinet.json_graph["S"]]

    def _transitions(self):
        return self.petrinet.json_graph["T"]

    def _input_edges(self):
        return self.petrinet.json_graph["I"]

    def _output_edges(self):
        return self.petrinet.json_graph["O"]

    def _parameter_names(self):
        return [t["tprop"]["parameter_name"] for t in self._transitions()]

    def _parameter_values(self):
        return {
            t["tprop"]["parameter_name"]: t["tprop"]["parameter_value"]
            for t in self._transitions()
        }

    def _parameters(self) -> List[Parameter]:
        param_names = self._parameter_names()
        param_values = self._parameter_values()
        params = [
            Parameter(
                name=p,
                lb=self.parameter_bounds[p][0],
                ub=self.parameter_bounds[p][1],
            )
            for p in param_names
            if self.parameter_bounds
            and p not in param_values
            and p in self.parameter_bounds
            and self.parameter_bounds[p]
        ]
        params += [
            Parameter(
                name=p,
                lb=param_values[p],
                ub=param_values[p],
            )
            for p in param_names
            if p in param_values
        ]

        return params

    def _num_flow_from_transition_to_state(
        self, state_index: int, transition_index: int
    ) -> int:
        return len(
            [
                edge
                for edge in self._output_edges()
                if edge["os"] == state_index and edge["ot"] == transition_index
            ]
        )

    def _num_flow_from_state_to_transition(
        self, state_index: int, transition_index: int
    ) -> int:
        return len(
            [
                edge
                for edge in self._input_edges()
                if edge["is"] == state_index and edge["it"] == transition_index
            ]
        )

    def _num_flow_from_transition(self, transition_index: int) -> int:
        return len(
            [
                edge
                for edge in self._output_edges()
                if edge["ot"] == transition_index
            ]
        )

    def _num_flow_into_transition(self, transition_index: int) -> int:
        return len(
            [
                edge
                for edge in self._input_edges()
                if edge["it"] == transition_index
            ]
        )

    def _flow_into_state_via_transition(
        self, state_index: int, transition_index: int
    ) -> float:
        num_flow_to_transition = self._num_flow_into_transition(
            transition_index
        )
        num_inflow = self._num_flow_from_transition_to_state(
            state_index, transition_index
        )
        num_transition_outputs = self._num_flow_from_transition(
            transition_index
        )
        if num_transition_outputs > 0:
            return (
                num_inflow / num_transition_outputs
            ) * num_flow_to_transition
        else:
            return 0

    def to_dot(self, values={}):
        """
        Create a dot object for visualizing the graph.

        Returns
        -------
        graphviz.Digraph
            The graph represented by self.
        """
        dot = graphviz.Digraph(
            name=f"petrinet",
            graph_attr={},
        )

        state_vars = self._state_vars()
        transitions = self._transitions()

        for v_index, var in enumerate(state_vars):
            state_var_name = var["sname"]
            for t_index, transition in enumerate(transitions):
                transition_name = f"{transition['tname']}({transition['tprop']['parameter_name']}) = {transition['tprop']['parameter_value']}"
                dot.node(transition_name, _attributes={"shape": "box"})
                # state var to transition
                for edge in self._input_edges():
                    if edge["is"] == v_index + 1 and edge["it"] == t_index + 1:
                        dot.edge(state_var_name, transition_name)
                # transition to state var
                for edge in self._output_edges():
                    if edge["os"] == v_index + 1 and edge["ot"] == t_index + 1:
                        flow = self._flow_into_state_via_transition(
                            v_index + 1, t_index + 1
                        ) / self._num_flow_from_transition_to_state(
                            v_index + 1, t_index + 1
                        )
                        dot.edge(
                            transition_name, state_var_name, label=f"{flow}"
                        )

        return dot
