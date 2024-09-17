from typing import Callable, Dict, List, Optional, Union

import graphviz
import sympy
from pydantic import BaseModel, ConfigDict
from pysmt.shortcuts import REAL, Div, Real, Symbol

from funman.utils.sympy_utils import (
    replace_reserved,
    substitute,
    sympy_to_pysmt,
    to_sympy,
)

from ..representation import Interval
from .generated_models.petrinet import Distribution
from .generated_models.petrinet import Model as GeneratedPetrinet
from .generated_models.petrinet import State, Transition
from .model import FunmanModel


class AbstractPetriNetModel(FunmanModel):
    _is_differentiable: bool = True

    def _num_flow_from_state_to_transition(
        self, state_id: Union[str, int], transition_id: Union[str, int]
    ) -> int:
        return len(
            [
                edge
                for edge in self._input_edges()
                if self._edge_source(edge) == state_id
                and self._edge_target(edge) == transition_id
            ]
        )

    def _num_flow_from_transition_to_state(
        self, state_id: Union[str, int], transition_id: Union[str, int]
    ) -> int:
        return len(
            [
                edge
                for edge in self._output_edges()
                if self._edge_source(edge) == transition_id
                and self._edge_target(edge) == state_id
            ]
        )

    def _num_flow_from_transition(self, transition_id: Union[str, int]) -> int:
        return len(
            [
                edge
                for edge in self._output_edges()
                if self._edge_source(edge) == transition_id
            ]
        )

    def _num_flow_into_transition(self, transition_id: Union[str, int]) -> int:
        return len(
            [
                edge
                for edge in self._input_edges()
                if self._edge_target(edge) == transition_id
            ]
        )

    def _flow_into_state_via_transition(
        self, state_id: Union[str, int], transition_id: Union[str, int]
    ) -> float:
        num_flow_to_transition = self._num_flow_into_transition(transition_id)
        num_inflow = self._num_flow_from_transition_to_state(
            state_id, transition_id
        )
        num_transition_outputs = self._num_flow_from_transition(transition_id)
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
        state_var_names = self._state_var_names()
        transitions = self._transitions()
        variable_values = self._variable_values()

        # Don't substitute initial state values for state variables, only parameters
        variable_values = {
            k: (None if k in state_var_names else v)
            for k, v in variable_values.items()
        }

        for _, var in enumerate(state_vars):
            state_var_id = self._state_var_id(var)
            state_var_name = self._state_var_name(var)
            for transition in transitions:
                transition_id = self._transition_id(transition)
                transition_parameters = self._transition_rate(transition)
                # transition_parameter_value = [
                #     self._parameter_values()[t] for t in transition_parameters
                # ]
                transition_parameter_value = [
                    substitute(t, variable_values)
                    for t in transition_parameters
                ]
                transition_name = f"{transition_id}({transition_parameters}) = {transition_parameter_value}"
                dot.node(transition_name, _attributes={"shape": "box"})
                # state var to transition
                for edge in self._input_edges():
                    if (
                        self._edge_source(edge) == state_var_id
                        and self._edge_target(edge) == transition_id
                    ):
                        dot.edge(state_var_name, transition_name)
                # transition to state var
                for edge in self._output_edges():
                    if (
                        self._edge_source(edge) == transition_id
                        and self._edge_target(edge) == state_var_id
                    ):
                        flow = self._flow_into_state_via_transition(
                            state_var_id, transition_id
                        ) / self._num_flow_from_transition_to_state(
                            state_var_id, transition_id
                        )
                        dot.edge(
                            transition_name, state_var_name, label=f"{flow}"
                        )

        return dot

    def calculate_normalization_constant(
        self, scenario: "AnalysisScenario", config: "FUNMANConfig"
    ) -> float:
        vars = self._state_var_names()
        values = {v: self._get_init_value(v, scenario, config) for v in vars}
        if all((v is not None and v.is_constant()) for v in values.values()):
            return float(sum(v.constant_value() for v in values.values()))
        else:
            raise Exception(
                f"Cannot calculate the normalization constant for {type(self)} because the initial state variables are not constants. Try setting the 'normalization_constant' in the configuration to constant."
            )

    def compartmental_constraints(
        self, population: Union[float, int], noise: float
    ) -> List["Constraint"]:
        from funman.representation.constraint import LinearConstraint

        vars = self._state_var_names()
        return [
            LinearConstraint(
                name="compartmental_constraint_population",
                additive_bounds={
                    "lb": population - noise,
                    "ub": population + noise,
                    "closed_upper_bound": True,
                },
                variables=vars,
                timepoints=Interval(lb=0.0),
                soft=False,
            )
        ] + [
            LinearConstraint(
                name=f"compartmental_{v}_nonnegative",
                additive_bounds={"lb": 0},
                variables=[v],
                timepoints=Interval(lb=0.0),
                soft=False,
            )
            for v in vars
        ]

    def derivative(
        self,
        var_name,
        t,
        values,
        params,
        var_to_value,
        param_to_value,
        get_lambda=False,
    ):  # var_to_value, param_to_value):
        # param_at_t = {p: pv(t).item() for p, pv in param_to_value.items()}
        # FIXME assumes each transition has only one rate
        # print(f"Calling with args {var_name}; {t}; {values}; {params}")
        if get_lambda:
            pos_rates = [
                self._transition_rate(trans, get_lambda=get_lambda)[0](
                    *values, *params
                )
                for trans in self._transitions()
                for var in trans.output
                if var_name == var
            ]
            neg_rates = [
                self._transition_rate(trans, get_lambda=get_lambda)[0](
                    *values, *params
                )
                for trans in self._transitions()
                for var in trans.input
                if var_name == var
            ]
        else:
            pos_rates = [
                self._transition_rate(trans)[0].evalf(
                    subs={**var_to_value, **param_to_value, "timer_t": t}, n=10
                )
                for trans in self._transitions()
                for var in trans.output
                if var_name == var
            ]
            neg_rates = [
                self._transition_rate(trans)[0].evalf(
                    subs={**var_to_value, **param_to_value, "timer_t": t}, n=10
                )
                for trans in self._transitions()
                for var in trans.input
                if var_name == var
            ]
        # print(f"Got rates {pos_rates} {neg_rates}")

        return sum(pos_rates) - sum(neg_rates)

    def gradient(self, t, y, *p):
        # FIXME support time varying paramters by treating parameters as a function
        var_to_value = {
            var: y[i] for i, var in enumerate(self._state_var_names())
        }
        print(f"y: {y}; t: {t}")
        param_to_value = {
            replace_reserved(param): p[i](t)[()]
            for i, param in enumerate(self._parameter_names())
        }
        # values = [
        #     y[i] for i, _ in enumerate(self._symbols())
        # ]
        params = [
            param_to_value[str(p)]
            for p in self._symbols()
            if str(p) in param_to_value
        ] + [t]

        grad = [
            self.derivative(
                var,
                t,
                y,
                params,
                var_to_value,
                param_to_value,
                get_lambda=False,
            )  # var_to_value, param_to_value)
            for var in self._state_var_names()
        ]
        print(f"vars: {self._state_var_names()}")
        print(f"gradient: {grad}")
        return grad


class GeneratedPetriNetModel(AbstractPetriNetModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    petrinet: GeneratedPetrinet
    _transition_rates_cache: Dict[str, Union[sympy.Expr, str]] = {}
    _observables_cache: Dict[str, Union[sympy.Expr, str]] = {}
    _transition_rates_lambda_cache: Dict[str, Union[Callable, str]] = {}

    def observables(self):
        return self.petrinet.semantics.ode.observables

    def is_timed_observable(self, observation_id):
        (_, e) = self.observable_expression(observation_id)
        vars = [str(e) for e in e.get_free_variables()]
        obs_state_vars = [v for v in vars if v in self._state_var_names()]
        return any(obs_state_vars)

    def observable_expression(self, observation_id):
        if observation_id not in self._observables_cache:
            observable = next(
                iter([o for o in self.observables() if o.id == observation_id])
            )
            self._observables_cache[observation_id] = (
                observable.expression,
                sympy_to_pysmt(
                    to_sympy(observable.expression, self._symbols())
                ),
            )
        return self._observables_cache[observation_id]

    def default_encoder(
        self, config: "FUNMANConfig", scenario: "AnalysisScenario"
    ) -> "Encoder":
        """
        Return the default Encoder for the model

        Returns
        -------
        Encoder
            SMT encoder for model
        """
        from funman.translate.petrinet import PetrinetEncoder

        return PetrinetEncoder(
            config=config,
            scenario=scenario,
        )

    def _time_var(self):
        if (
            hasattr(self.petrinet, "semantics")
            and hasattr(self.petrinet.semantics, "ode")
            and hasattr(self.petrinet.semantics.ode, "time")
        ):
            return self.petrinet.semantics.ode.time
        else:
            return None

    def _time_var_id(self, time_var):
        if time_var:
            return f"timer_{time_var.id}"
        else:
            return None

    def _symbols(self):
        symbols = self._state_var_names() + self._parameter_names()
        if self._time_var():
            symbols += [self._time_var().id]
        return symbols

    def _get_init_value(
        self, var: str, scenario: "AnalysisScenario", config: "FUNMANConfig"
    ):
        value = FunmanModel._get_init_value(self, var, scenario, config)
        if value is None:
            if hasattr(self.petrinet.semantics, "ode"):
                initials = self.petrinet.semantics.ode.initials
                value = next(i.expression for i in initials if i.target == var)
            else:
                value = f"{var}0"

        try:  # to cast to float
            value = float(value)
        except:
            pass

        if isinstance(value, float):
            value = Real(value)
        if isinstance(value, int):
            value = Real(float(value))
        elif isinstance(value, str):
            expr = to_sympy(value, self._symbols())
            if expr.is_symbol:
                value = Symbol(value, REAL)
            else:
                value = sympy_to_pysmt(expr)

        if scenario.normalization_constant and config.normalize:
            value = Div(value, Real(scenario.normalization_constant))

        return value

    def _parameter_lb(self, param_name: str):
        return next(
            (
                self._try_float(p.distribution.parameters["minimum"])
                if p.distribution
                else p.value
            )
            for p in self.petrinet.semantics.ode.parameters
            if p.id == param_name
        )

    def _parameter_ub(self, param_name: str):
        return next(
            (
                self._try_float(p.distribution.parameters["maximum"])
                if p.distribution
                else p.value
            )
            for p in self.petrinet.semantics.ode.parameters
            if p.id == param_name
        )

    def _state_vars(self) -> List[State]:
        return self.petrinet.model.states

    def _state_var_names(self) -> List[str]:
        return [self._state_var_name(s) for s in self._state_vars()]

    def _transitions(self) -> List[Transition]:
        return self.petrinet.model.transitions

    def _state_var_name(self, state_var: State) -> str:
        return state_var.id

    def _input_edges(self):
        return [(i, t.id) for t in self._transitions() for i in t.input]

    def _edge_source(self, edge):
        return edge[0]

    def _edge_target(self, edge):
        return edge[1]

    def _output_edges(self):
        return [(t.id, o) for t in self._transitions() for o in t.output]

    def _transition_rate(self, transition, sympify=False, get_lambda=False):
        if hasattr(self.petrinet.semantics, "ode"):
            if transition.id not in self._transition_rates_cache:
                t_rates = [
                    (
                        to_sympy(r.expression, self._symbols())
                        # if not any(
                        #     p == r.expression for p in self._parameter_names()
                        # )
                        # else r.expression
                    )
                    for r in self.petrinet.semantics.ode.rates
                    if r.target == transition.id
                ]
                time_var = self._time_var()
                if time_var:
                    t_rates = [
                        t.subs(
                            {
                                self._time_var().id: f"timer_{self._time_var().id}"
                            }
                        )
                        for t in t_rates
                    ]
                unreserved_symbols = [
                    replace_reserved(s) for s in self._symbols()
                ]
                # convert "t" to "timer_t"
                unreserved_symbols[-1] = self._time_var_id(self._time_var())
                t_rates_lambda = [
                    sympy.lambdify(unreserved_symbols, t) for t in t_rates
                ]
                self._transition_rates_cache[transition.id] = t_rates
                self._transition_rates_lambda_cache[transition.id] = (
                    t_rates_lambda
                )
            return (
                self._transition_rates_cache[transition.id]
                if not get_lambda
                else self._transition_rates_lambda_cache[transition.id]
            )
        else:
            return transition.id

    def _transition_id(self, transition):
        return transition.id

    def _state_var_id(self, state_var):
        return self._state_var_name(state_var)

    def _parameter_names(self):
        if hasattr(self.petrinet.semantics, "ode"):
            return [p.id for p in self.petrinet.semantics.ode.parameters]
        else:
            # Create a parameter for each transition and initial state variable
            return [t.id for t in self.petrinet.model.transitions] + [
                f"{s.id}0" for s in self.petrinet.model.states
            ]

    def _parameter_values(self):
        if hasattr(self.petrinet.semantics, "ode"):
            return {
                p.id: p.value for p in self.petrinet.semantics.ode.parameters
            }
        else:
            return {}

    def _variable_values(self):
        values = {}
        if hasattr(self.petrinet.semantics, "ode"):
            for p in self.petrinet.semantics.ode.parameters:
                values[p.id] = p.value
            for p in self.petrinet.semantics.ode.initials:
                values[p.target] = p.expression
                try:
                    values[p.target] = float(values[p.target])
                except:
                    pass

        return values

    def contract_parameters(
        self, parameter_bounds: Dict[str, Interval]
    ) -> GeneratedPetrinet:
        contracted_model = self.petrinet.copy(deep=True)

        for param in contracted_model.semantics.ode.parameters:
            new_bounds = parameter_bounds[param.id]
            if param.distribution:
                param.distribution.parameters["minimum"] = max(
                    new_bounds.lb,
                    float(param.distribution.parameters["minimum"]),
                )
                param.distribution.parameters["maximum"] = min(
                    new_bounds.ub,
                    float(param.distribution.parameters["maximum"]),
                )
            else:
                param.distribution = Distribution(
                    parameters={
                        "minimum": new_bounds.lb,
                        "maximum": new_bounds.ub,
                    },
                    type="StandardUniform1",
                )

        return contracted_model


class PetrinetDynamics(BaseModel):
    json_graph: Dict[
        str,
        List[
            Dict[
                str,
                Optional[
                    Union[
                        Dict[str, Optional[Union[str, bool, float]]],
                        int,
                        str,
                        float,
                    ]
                ],
            ]
        ],
    ]

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)
    #     self.json_graph = kwargs["json_graph"]
    #     self._initialize_from_json()


class PetrinetModel(AbstractPetriNetModel):
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
        return [self._state_var_name(s) for s in self.petrinet.json_graph["S"]]

    def _state_var_name(self, state_var: Dict) -> str:
        return state_var["sname"]

    def _transitions(self):
        return self.petrinet.json_graph["T"]

    def _input_edges(self):
        return self.petrinet.json_graph["I"]

    def _output_edges(self):
        return self.petrinet.json_graph["O"]

    def _edge_source(self, edge):
        return edge["is"] if "is" in edge else edge["ot"]

    def _edge_target(self, edge):
        return edge["it"] if "it" in edge else edge["os"]

    def _transition_rate(self, transition):
        return self._encode_state_var(transition["tprop"]["parameter_name"])

    def _transition_id(self, transition):
        return next(
            i + 1
            for i, s in enumerate(self._transitions())
            if s["tname"] == transition["tname"]
        )

    def _state_var_id(self, state_var):
        return next(
            i + 1
            for i, s in enumerate(self._state_vars())
            if s["sname"] == state_var["sname"]
        )

    def _parameter_names(self):
        return [t["tprop"]["parameter_name"] for t in self._transitions()]

    def _parameter_values(self):
        return {
            t["tprop"]["parameter_name"]: t["tprop"]["parameter_value"]
            for t in self._transitions()
        }
