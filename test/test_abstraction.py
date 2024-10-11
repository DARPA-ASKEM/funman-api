import logging
import os
import sys
import unittest

import sympy

from funman.api.run import Runner
from funman.utils.sympy_utils import SympyBoundedSubstituter, to_sympy


class TestUseCases(unittest.TestCase):
    l = logging.Logger(__name__)

    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        self.l.level = logging.getLogger().level
        self.l.handlers.append(logging.StreamHandler(sys.stdout))

    def test_minimize_expression(self):
        tests = [
            {
                "input": ["S", "- S * I * beta/N"],
                "bound": "lb",
                "expected_output": "-I_ub*S_lb*beta_ub/N_lb",
            },
            {
                "input": ["S", "- S * I * beta/N"],
                "bound": "ub",
                "expected_output": "-I_lb*S_ub*beta_lb/N_ub",
            },
            {
                "input": ["S", "- S * I * beta"],
                "bound": "lb",
                "expected_output": "-I_ub*S_lb*beta_ub",
            },
            {
                "input": ["S", "- S * I * beta"],
                "bound": "ub",
                "expected_output": "-I_lb*S_ub*beta_lb",
            },
            {
                "input": ["I", "S * I * beta - I * gamma"],
                "bound": "lb",
                "expected_output": "I_lb*S_lb*beta_lb - I_lb*gamma_ub",
            },
            {
                "input": ["I", "S * I * beta - I * gamma"],
                "bound": "ub",
                "expected_output": "I_ub*S_ub*beta_ub - I_ub*gamma_lb",
            },
            {
                "input": ["R", "I * gamma"],
                "bound": "lb",
                "expected_output": "I_lb*gamma_lb",
            },
            {
                "input": ["I", "I * gamma"],
                "bound": "ub",
                "expected_output": "I_ub*gamma_ub",
            },
        ]

        str_symbols = ["S", "I", "R", "beta", "gamma", "N"]
        symbols = {s: sympy.Symbol(s) for s in str_symbols}
        bound_symbols = {
            s: {"lb": f"{s}_lb", "ub": f"{s}_ub"} for s in str_symbols
        }
        substituter = SympyBoundedSubstituter(
            bound_symbols=bound_symbols, str_to_symbol=symbols
        )

        for test in tests:
            with self.subTest(f"{test['bound']}({test['input']})"):
                test_fn = (
                    substituter.minimize
                    if test["bound"] == "lb"
                    else substituter.maximize
                )
                test_output = test_fn(*test["input"])
                # self.l.debug(f"Minimized: [{infection_rate}], to get expression: [{test_output}]")
                assert (
                    str(test_output) == test["expected_output"]
                ), f"Failed to create the expected expression: [{test['expected_output']}], got [{test_output}]"

    def test_stratify(self):
        RESOURCES = os.path.join("resources")
        EXAMPLE_DIR = os.path.join(
            RESOURCES, "amr", "petrinet", "monthly-demo", "2024-09"
        )
        REQUEST_PATH = os.path.join(EXAMPLE_DIR, "sir_request1.json")
        BASE_MODEL_PATH = os.path.join(EXAMPLE_DIR, "sir.json")
        runner = Runner()
        base_result = runner.run(BASE_MODEL_PATH, REQUEST_PATH)

        assert (
            base_result
        ), f"Could not generate a result for model: [{BASE_MODEL_PATH}], request: [{REQUEST_PATH}]"

        (base_model, _) = runner.get_model(BASE_MODEL_PATH)

        # Stratify Base model
        stratified_model = base_model  # FIXME

        stratified_result = runner.run(stratified_model, REQUEST_PATH)

        assert (
            stratified_result
        ), f"Could not generate a result for stratified version of model: [{BASE_MODEL_PATH}], request: [{REQUEST_PATH}]"

        # Abstract and bound stratified Base model
        abstract_model = stratified_model  # FIXME
        bounded_abstract_model = abstract_model  # FIXME

        bounded_abstract_result = runner.run(
            bounded_abstract_model, REQUEST_PATH
        )

        assert (
            bounded_abstract_result
        ), f"Could not generate a result for bounded abstracted stratified version of model: [{BASE_MODEL_PATH}], request: [{REQUEST_PATH}]"

        # # Modify request parameters
        # request_parameters = stratified_request.parameters
        # req_beta_1 = next(p for p in request_parameters if p.name == "beta_1")
        # req_beta_2 = next(p for p in request_parameters if p.name == "beta_2")
        # req_beta_1.interval = Interval(lb=beta_1.value, ub = beta_1.value, closed_upper_bound = True)
        # req_beta_2.interval = Interval(lb=beta_2.value, ub = beta_2.value, closed_upper_bound = True)

        # # stratified_request = FunmanWorkRequest()
        # setup_common(stratified_request, timepoints, debug=True, mode=MODE, synthesize=False,dreal_precision=1)
        # results = run(stratified_request, stratified_model_str, models)
        # report(results, stratified_model_str, stratified_model._state_var_names() + stratified_model._observable_names(), request_results, request_params)
        # stratified_model.to_dot()


if __name__ == "__main__":
    unittest.main()
