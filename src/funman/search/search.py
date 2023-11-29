import datetime
import logging
import threading
from abc import ABC, abstractmethod
from decimal import Decimal
from multiprocessing import Array, Queue, Value
from queue import Queue as SQueue
from typing import Callable, List, Optional, Union

import pysmt
from pydantic import BaseModel, ConfigDict
from pysmt.shortcuts import Solver
from pysmt.solvers.solver import Model as pysmtModel

from funman import Box, Interval, ModelParameter
from funman.translate.translate import EncodingSchedule

from ..config import FUNMANConfig
from ..representation.explanation import BoxExplanation
from ..scenario.scenario import AnalysisScenario

l = logging.getLogger(__name__)


class SearchStatistics(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    _multiprocessing: bool = False
    _num_true: int = 0
    _num_false: int = 0
    _num_unknown: int = 0
    _residuals: SQueue = None
    _current_residual: float = 0.0
    _last_time: List[datetime.datetime] = []
    _iteration_time: SQueue = None
    _iteration_operation: SQueue = None

    def __init__(self, **kw):
        super().__init__(**kw)
        self._residuals = SQueue()
        self._iteration_time = SQueue()
        self._iteration_operation = SQueue()


class SearchStaticsMP(SearchStatistics):
    _multiprocessing: bool = True
    _num_true: Value = 0
    _num_false: Value = 0
    _num_unknown: Value = 0
    _residuals: Queue = None
    _current_residual: Value = 0.0
    _last_time: Array = None
    _iteration_time: Queue = None
    _iteration_operation: Queue = None

    def __init__(self, **kw):
        super().__init__(**kw)

        manager = kw["manager"]
        self._multiprocessing = manager is not None
        self._num_true = manager.Value("i", 0)
        self._num_false = manager.Value("i", 0)
        self._num_unknown = manager.Value("i", 0)
        self._residuals = manager.Queue()
        self._current_residual = manager.Value("d", 0.0)
        self._last_time = manager.Array("u", "")
        self._iteration_time = manager.Queue()
        self._iteration_operation = manager.Queue()


class SearchEpisode(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    schedule: EncodingSchedule
    problem: AnalysisScenario
    config: "FUNMANConfig"
    statistics: SearchStatistics = None
    _model: pysmt.solvers.solver.Model = None

    def num_parameters(self):
        return len(self.problem.parameters)

    def _initial_box(self, schedule: EncodingSchedule) -> Box:
        box = Box(
            bounds={
                p.name: p.interval.model_copy(deep=True)
                for p in self.problem.parameters
                if (isinstance(p, ModelParameter))
            },
            schedule=schedule,
        )
        box.bounds["timestep"] = Interval(
            lb=0, ub=len(schedule.timepoints) - 1, closed_upper_bound=True
        )
        box.bounds["timestep"].original_width = Decimal(
            len(schedule.timepoints) - 1
        )

        return box


class Search(ABC):
    def __init__(self) -> None:
        self.episodes = []

    @abstractmethod
    def search(
        self,
        problem: "AnalysisScenario",
        config: Optional["FUNMANConfig"] = None,
        haltEvent: Optional[threading.Event] = None,
        resultsCallback: Optional[Callable[["ParameterSpace"], None]] = None,
    ) -> SearchEpisode:
        pass

    def invoke_solver(self, s: Solver) -> Union[pysmtModel, BoxExplanation]:
        l.trace("Invoking solver ...")
        result = s.solve()
        l.trace(f"Solver result = {result}")
        if result:
            result = s.get_model()
        else:
            result = BoxExplanation()
            result._expression = s.get_unsat_core()

        return result
