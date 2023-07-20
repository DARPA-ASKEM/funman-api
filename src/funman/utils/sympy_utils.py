from fractions import Fraction
from functools import reduce
from numbers import Rational
import math
from typing import Dict, List, Union
import logging

import pysmt.operators as op
import pysmt.typing as types
import sympy
from pysmt.formula import FNode, FormulaManager
from pysmt.shortcuts import (
    REAL,
    Div,
    Minus,
    Plus,
    Pow,
    Real,
    Symbol,
    Times,
    get_env,
)

l = logging.getLogger(__name__)
l.setLevel(logging.INFO)


class FUNMANFormulaManager(FormulaManager):
    """FormulaManager is responsible for the creation of all formulae."""

    def __init__(self, formula_manager, env=None):
        # Copy formula_manager, and don't call super().__init__()
        self.env = formula_manager.env
        self.formulae = formula_manager.formulae
        self.symbols = formula_manager.symbols
        self._fresh_guess = formula_manager._fresh_guess
        self.get_type = formula_manager.get_type
        self._next_free_id = formula_manager._next_free_id

        self.int_constants = formula_manager.int_constants
        self.real_constants = formula_manager.real_constants
        self.string_constants = formula_manager.string_constants

        self.true_formula = formula_manager.true_formula
        self.false_formula = formula_manager.false_formula

    def Pow(self, base, exponent):
        """Creates the n-th power of the base.

        The exponent must be a constant.
        """

        # Funman allows expressions in base, thus the override of the super Pow
        # if not exponent.is_constant():
        #     raise PysmtValueError("The exponent of POW must be a constant.", exponent)

        if base.is_constant() and exponent.is_constant():
            val = base.constant_value() ** exponent.constant_value()
            if base.is_constant(types.REAL):
                return self.Real(val)
            else:
                assert base.is_constant(types.INT)
                return self.Int(val)
        return self.create_node(node_type=op.POW, args=(base, exponent))


def series_approx(expr: sympy.Expr, vars: List[sympy.Symbol] = []) -> sympy.Expr:
    sympy_symbols = [sympy.symbols(str(v)) for v in vars]
    series_expr = reduce(
        lambda v1, v2: sympy.series(v1, v2, n=4).removeO(), sympy_symbols, expr
    )
    return series_expr


def sympy_subs(
    expr: sympy.Expr, substitution: Dict[str, Union[float, str]]
) -> sympy.Expr:
    return expr.subs(substitution)


reserved_words = ["lambda"]


def has_reserved(str_expr, rw):
    return rw in str_expr and f"funman_{rw}" not in str_expr


def replace_reserved(str_expr):
    for rw in reserved_words:
        if isinstance(str_expr, str) and has_reserved(str_expr, rw):
            str_expr = str_expr.replace(rw, f"funman_{rw}")
    return str_expr


def to_sympy(
    str_expr: str,
    symbols: List[str],
) -> sympy.Expr:
    unreserved_symbols = [replace_reserved(s) for s in symbols]
    expr = sympy.sympify(
        replace_reserved(str_expr), {s: sympy.symbols(s) for s in unreserved_symbols}
    )
    return expr


def substitute(str_expr: str, values: Dict[str, Union[float, str]]):
    # Set which substrings are symbols
    symbols = {s: sympy.Symbol(s) for s in values}

    # Get expression
    expr = to_sympy(str_expr, list(values.values()))

    # Get variable values
    values_syms = {s: values[str(s)] for s in symbols}
    subs = [(sym, val) for sym, val in values_syms.items() if val is not None]

    # substitute
    sub_expr = expr.subs(subs)
    return sub_expr


def rate_expr_to_pysmt(expr: Union[str, sympy.Expr], state=None):
    env_symbols = get_env().formula_manager.symbols
    f = to_sympy(expr, [str(s) for s in env_symbols])
    p: FNode = sympy_to_pysmt(f)

    if state:  # Map symbols in p to state indexed versions (e.g., I to I_5)
        symbol_to_state_var = {env_symbols[s]: state[str(s)] for s in state}

        if "timer_t" in state:
            # Replace mapping timer_t: timer_t_k with t: timer_t_k
            symbol_to_state_var[Symbol("t", REAL)] = state["timer_t"]

        p_sub = p.substitute(symbol_to_state_var)
        return p_sub
    else:
        return p


def sympy_to_pysmt(expr):
    func = expr.func
    if func.is_Mul:
        return sympy_to_pysmt_op(Times, expr)
    elif func.is_Add:
        return sympy_to_pysmt_op(Plus, expr)
    elif func.is_Symbol:
        return sympy_to_pysmt_symbol(Symbol, expr, op_type=REAL)
    elif func.is_Pow:
        return sympy_to_pysmt_pow(expr)
    elif isinstance(expr, sympy.exp):
        return Pow(sympy_to_pysmt_real(math.e), sympy_to_pysmt(expr.exp))
    elif expr.is_constant():
        return sympy_to_pysmt_real(expr)
    else:
        raise Exception(f"Could not convert expression: {expr}")


def sympy_to_pysmt_op(op, expr):
    terms = [sympy_to_pysmt(arg) for arg in expr.args]
    return op(terms)


def sympy_to_pysmt_pow(expr):
    base = expr.args[0]
    exponent = expr.args[1]
    return Pow(sympy_to_pysmt(base), sympy_to_pysmt(exponent))


def sympy_to_pysmt_real(expr, numerator_digits=6):
    # check if underflow or overflow
    if not isinstance(expr, float) and (
        (expr != 0.0 and float(expr) == 0.0)
        or (not expr.is_infinite and abs(float(expr)) == math.inf)
    ):
        # going from sympy to python to pysmt will lose precision
        # need to convert to a rational first
        r_expr = sympy.Rational(expr)
        return Div(Real(r_expr.numerator), Real(r_expr.denominator)).simplify()
    else:
        return Real(float(expr))

    # rnd_expr = sympy.Float(expr, 5)
    # r_expr = sympy.Rational(rnd_expr)
    # f_expr = Fraction(int(r_expr.numerator), int(r_expr.denominator))

    # max_denominator = math.pow(10, (len(str(r_expr.denominator)) - len(str(abs(r_expr.numerator)))) + max(numerator_digits, 1)+1)
    # try:
    #     trunc_f_expr = f_expr.limit_denominator(max_denominator=max_denominator)
    # except Exception as e:
    #     l.exception(f"max_denominator = {max_denominator} is not large enough to limit the denominator of {expr} during conversion from sympy to pysmt")

    # r_value = Div(Real(trunc_f_expr.numerator), Real(trunc_f_expr.denominator)).simplify()

    # r_value = Real(float(expr))

    # return r_value


def sympy_to_pysmt_symbol(op, expr, op_type=None):
    return op(str(expr), op_type) if op_type else op(str(expr))


if __name__ == "__main__":
    symbols = {
        "I": sympy.Symbol("I"),
        "S": sympy.Symbol("S"),
        "N": sympy.Symbol("N"),
    }
    exprs = [
        "I*S",
        "I*S*kappa*(beta_c + (-beta_c + beta_s)/(1 + exp(-k*(-t + t_0))))/N",
    ]
    for e in exprs:
        f = sympy.sympify(e, symbols)
        p: FNode = sympy_to_pysmt(f)
        print(f"Read: {e}")
        print(f"Sympy parsed: {f}")
        print(f"Pysmt parse: {p.to_smtlib(daggify=False)}")
        print("*" * 80)
