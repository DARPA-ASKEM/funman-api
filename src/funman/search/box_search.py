"""
This module defines the BoxSearch class and supporting classes.

"""
import logging
import multiprocessing as mp
import os
import traceback
from multiprocessing.synchronize import Condition, Event, Lock
from queue import Empty
from queue import Queue as QueueSP
from typing import List, Optional

from pysmt.formula import FNode
from pysmt.logics import QF_NRA
from pysmt.shortcuts import And, Not, Solver, get_model

from funman.representation.representation import (
    LABEL_DROPPED,
    LABEL_FALSE,
    LABEL_TRUE,
    LABEL_UNKNOWN,
    Interval,
)
from funman.search import Box, ParameterSpace, Point, Search, SearchEpisode
from funman.search.search import SearchStaticsMP, SearchStatistics
from funman.utils.smtlib_utils import smtlibscript_from_formula_list

LOG_LEVEL = logging.INFO

l = logging.getLogger(__file__)
l.setLevel(LOG_LEVEL)


class BoxSearch(Search):
    """
    Box search algorithm.
    """

    def _split(self, box: Box, episode: BoxSearchEpisode, points=None):
        normalize = episode.problem._original_parameter_widths
        b1, b2 = box.split(points=points, normalize=normalize)
        episode.statistics._iteration_operation.put("s")
        return episode._add_unknown([b1, b2])

    def _logger(self, config, process_name=None):
        if config.number_of_processes > 1:
            l = mp.log_to_stderr()
            if process_name:
                l.name = process_name
            l.setLevel(LOG_LEVEL)
        else:
            if not process_name:
                process_name = "BoxSearch"
            l = logging.Logger(process_name)
        return l

    def _handle_empty_queue(
        self, process_name, episode, more_work, idle_mutex, idle_flags
    ):
        if episode.config.number_of_processes > 1:
            # set this processes idle flag and check all the other process idle flags
            # doing so under the idle_mutex to ensure the flags are not under active change
            with idle_mutex:
                idle_flags[id].set()
                should_exit = all(f.is_set() for f in idle_flags)

            # all worker processes appear to be idle
            if should_exit:
                # one last check to see if there is work to be done
                # which would be an error at this point in the code
                if episode._unknown_boxes.qsize() != 0:
                    l.error(
                        f"{process_name} found more work while preparing to exit"
                    )
                    return False
                l.info(f"{process_name} is exiting")
                # tell other worker processing to check again with the expectation
                # that they will also resolve to exit
                with more_work:
                    more_work.notify()
                # break of the while True and allow the process to exit
                return True

            # wait for notification of more work
            l.info(f"{process_name} is awaiting work")
            with more_work:
                more_work.wait()

            # clear the current processes idle flag under the idle_mutex
            with idle_mutex:
                idle_flags[id].clear()

            return False
        else:
            return True

    def _initialize_box(self, solver, box, episode):
        solver.push(1)
        formula = episode.problem._smt_encoder.box_to_smt(box)
        episode._formula_stack.append(formula)
        solver.add_assertion(formula)

    def _setup_false_query(self, solver, episode):
        """
        Setup the assumptions so that satisfying the formulas requires that  either the model or the query is false

        Parameters
        ----------
        solver : Solver
            pysmt solver object
        episode : episode
            data for the current search
        """
        solver.push(1)
        formula = And(
            episode.problem._assume_model,
            Not(episode.problem._assume_query),
        )
        episode._formula_stack.append(formula)
        solver.add_assertion(formula)

    def store_smtlib(self, episode, box, filename="dbg.smt2"):
        with open(filename, "w") as f:
            print(f"Saving smtlib file: {filename}")
            smtlibscript_from_formula_list(
                episode._formula_stack,
                logic=QF_NRA,
            ).serialize(f, daggify=False)

    def _setup_true_query(self, solver, episode):
        """
        Setup the assumptions so that satisfying the formulas requires that both the model and the query are true

        Parameters
        ----------
        solver : Solver
            pysmt solver object
        episode : episode
            data for the current search
        """
        solver.push(1)
        formula = And(
            episode.problem._assume_model, episode.problem._assume_query
        )
        episode._formula_stack.append(formula)
        solver.add_assertion(formula)

    def _get_false_points(self, solver, episode, box, rval):
        false_points = [
            fp for fp in episode._false_points if box.contains_point(fp)
        ]
        if len(false_points) == 0:
            # If no cached point, then attempt to generate one
            # print("Checking false query")
            self._setup_false_query(solver, episode)
            if episode.config.save_smtlib:
                self.store_smtlib(
                    episode, box, filename=f"fp_{episode._iteration}.smt2"
                )
            if solver.solve():
                # Record the false point
                res = solver.get_model()
                false_points = [episode._extract_point(res)]
                for point in false_points:
                    episode._add_false_point(point)
                    rval.put(point.dict())
            solver.pop(1)  # Remove false query
            episode._formula_stack.pop()

        return false_points

    def _get_true_points(self, solver, episode, box, rval):
        true_points = [
            tp for tp in episode._true_points if box.contains_point(tp)
        ]
        if len(true_points) == 0:
            # If no cached point, then attempt to generate one
            # print("Checking true query")
            self._setup_true_query(solver, episode)
            if episode.config.save_smtlib:
                self.store_smtlib(
                    episode, box, filename=f"tp_{episode._iteration}.smt2"
                )
            # self.store_smtlib(episode, box)
            if solver.solve():
                # self.store_smtlib(
                #     episode, box, filename=f"tp_{episode._iteration}.smt2"
                # )
                # Record the true point
                res1 = solver.get_model()
                true_points = [episode._extract_point(res1)]
                for point in true_points:
                    episode._add_true_point(point)
                    rval.put(point.dict())
            solver.pop(1)  # Remove true query
            episode._formula_stack.pop()

        return true_points

    def _expand(
        self,
        rval,
        episode: BoxSearchEpisode,
        idx: Optional[int] = None,
        more_work: Optional[Condition] = None,
        idle_mutex: Optional[Lock] = None,
        idle_flags: Optional[List[Event]] = None,
        handler: Optional["ResultHandler"] = None,
        all_results=None,
    ):
        """
        A single search process will evaluate and expand the boxes in the
        episode.unknown_boxes queue.  The processes exit when the queue is
        empty.  For each box, the algorithm checks whether the box contains a
        false (infeasible) point.  If it contains a false point, then it checks
        if the box contains a true point.  If a box contains both a false and
        true point, then the box is split into two boxes and both are added to
        the unknown_boxes queue.  If a box contains no false points, then it is
        a true_box (all points are feasible).  If a box contains no true points,
        then it is a false_box (all points are infeasible).

        The return value is pushed onto the rval queue to end the process's work
        within the method.  The return value is a Dict[str, List[Box]] type that
        maps the "true_boxes" and "false_boxes" to a list of boxes in each set.
        Each box in these sets is unique by design.

        Parameters
        ----------
        rval : Queue
            Return value shared queue
        episode : BoxSearchEpisode
            Shared search data and statistics.
        """
        process_name = f"Expander_{idx}_p{os.getpid()}"
        l = self._logger(episode.config, process_name=process_name)

        try:
            if episode.config.solver == "dreal":
                opts = {
                    "dreal_precision": episode.config.dreal_precision,
                    "dreal_log_level": episode.config.dreal_log_level,
                    "dreal_mcts": episode.config.dreal_mcts,
                }
            else:
                opts = {}
            with Solver(
                name=episode.config.solver,
                logic=QF_NRA,
                solver_options=opts,
            ) as solver:
                l.info(f"{process_name} entering process loop")
                print("Starting initializing dynamics of model")
                self._initialize_encoding(solver, episode)
                print("Initialized dynamics of model")
                while True:
                    try:
                        box: Box = episode._get_unknown()
                        rval.put(box.dict())
                        l.info(f"{process_name} claimed work")
                    except Empty:
                        exit = self._handle_empty_queue(
                            process_name,
                            episode,
                            more_work,
                            idle_mutex,
                            idle_flags,
                        )
                        if exit:
                            break
                        else:
                            continue
                    else:
                        self._initialize_box(solver, box, episode)

                        # Check whether box intersects t (true region)
                        # First see if a cached false point exists in the box
                        true_points = self._get_true_points(
                            solver, episode, box, rval
                        )

                        if len(true_points) > 0:
                            # box intersects f (true region)

                            # Check whether box intersects f (false region)
                            # First see if a cached false point exists in the box
                            false_points = self._get_false_points(
                                solver, episode, box, rval
                            )

                            if len(false_points) > 0:
                                # box intersects f (false region)

                                # box intersects both t and f, so it must be split
                                # use the true and false points to compute a midpoint
                                if self._split(
                                    box,
                                    episode,
                                    points=[true_points, false_points],
                                ):
                                    l.info(f"{process_name} produced work")
                                else:
                                    rval.put(box.dict())
                                if episode.config.number_of_processes > 1:
                                    # FIXME This would only be none when
                                    # the number of processes is 1. This
                                    # can be done more cleanly.
                                    if more_work:
                                        with more_work:
                                            more_work.notify_all()
                                print(f"Split({box})")
                            else:
                                # box does not intersect f, so it is in t (true region)
                                episode._add_true(box)
                                rval.put(box.dict())
                                print(f"+++ True({box})")
                        else:
                            # box is a subset of f (intersects f but not t)
                            episode._add_false(
                                box
                            )  # TODO consider merging lists of boxes
                            rval.put(box.dict())
                            print(f"--- False({box})")
                        solver.pop(1)  # Remove box from solver
                        episode._formula_stack.pop()
                        episode._on_iteration()
                        if handler:
                            all_results = handler(
                                rval, episode.config, all_results
                            )
                        l.info(f"{process_name} finished work")
                solver.pop(1)  # Remove the dynamics from the solver
                episode._formula_stack.pop()
        except KeyboardInterrupt:
            l.info(f"{process_name} Keyboard Interrupt")
        except Exception:
            l.error(traceback.format_exc())

    def _run_handler(self, rval, config: "FUNMANConfig"):
        """
        Execute the process that does final processing of the results of expand()
        """
        l = self._logger(config, process_name=f"search_process_result_handler")

        handler: ResultHandler = config._handler
        true_boxes = []
        false_boxes = []
        dropped_boxes = []
        true_points = []
        false_points = []
        break_on_interrupt = False
        try:
            handler.open()
            while True:
                try:
                    result: dict = rval.get(timeout=config.queue_timeout)
                except Empty:
                    continue
                except KeyboardInterrupt:
                    if break_on_interrupt:
                        break
                    break_on_interrupt = True
                else:
                    if result is None:
                        break

                    # TODO this is a bit of a mess and can likely be cleaned up
                    inst = ParameterSpace.decode_labeled_object(result)
                    label = inst.label
                    if isinstance(inst, Box):
                        if label == "true":
                            true_boxes.append(inst)
                        elif label == "false":
                            false_boxes.append(inst)
                        elif label == "dropped":
                            dropped_boxes.append(inst)
                        else:
                            l.warning(f"Skipping Box with label: {label}")
                    elif isinstance(inst, Point):
                        if label == "true":
                            true_points.append(inst)
                        elif label == "false":
                            false_points.append(inst)
                        else:
                            l.warning(f"Skipping Point with label: {label}")
                    else:
                        l.error(f"Skipping invalid object type: {typ}")

                    try:
                        handler.process(result)
                    except Exception:
                        l.error(traceback.format_exc())

        except Exception as error:
            l.error(error)
        finally:
            handler.close()
        return {
            "true_boxes": true_boxes,
            "false_boxes": false_boxes,
            "dropped_boxes": dropped_boxes,
            "true_points": true_points,
            "false_points": false_points,
        }

    def _run_handler_step(self, rval, config: "FUNMANConfig", all_results):
        """
        Execute one step of processing the results of expand()
        """
        l = self._logger(config, process_name=f"search_process_result_handler")

        handler: ResultHandler = config._handler
        # true_boxes = []
        # false_boxes = []
        # true_points = []
        # false_points = []
        break_on_interrupt = False
        try:
            # handler.open()
            while True:
                try:
                    result: dict = rval.get(timeout=config.queue_timeout)
                except Empty:
                    break
                except KeyboardInterrupt:
                    if break_on_interrupt:
                        break
                    break_on_interrupt = True
                else:
                    if result is None:
                        break

                    # TODO this is a bit of a mess and can likely be cleaned up
                    try:
                        inst = ParameterSpace.decode_labeled_object(result)
                    except:
                        l.error(f"Skipping invalid object")
                        continue

                    label = inst.label
                    if isinstance(inst, Box):
                        if label == "true":
                            all_results["true_boxes"].append(inst)
                        elif label == "false":
                            all_results["false_boxes"].append(inst)
                        elif label == "dropped":
                            all_results["dropped_boxes"].append(inst)
                        elif label == "unknown":
                            pass  # Allow unknown boxes for plotting
                        else:
                            l.warning(f"Skipping Box with label: {label}")
                    elif isinstance(inst, Point):
                        if label == "true":
                            all_results["true_points"].append(inst)
                        elif label == "false":
                            all_results["false_points"].append(inst)
                        else:
                            l.warning(f"Skipping Point with label: {label}")
                    else:
                        l.error(f"Skipping invalid object type: {type(inst)}")
                        continue

                    try:
                        handler.process(result)
                    except Exception:
                        l.error(traceback.format_exc())

        except Exception as error:
            l.error(error)
        finally:
            if config._wait_action is not None:
                config._wait_action.run()
            # handler.close()
        return all_results

    def search(
        self, problem: "AnalysisScenario", config: "FUNMANConfig"
    ) -> ParameterSpace:
        """
        The BoxSearch.search() creates a BoxSearchEpisode object that stores the
        search progress.  This method is the entry point to the search that
        spawns several processes to parallelize the evaluation of boxes in the
        BoxSearch.expand() method.  It treats the zeroth process as a special
        process that is allowed to initialize the search and plot the progress
        of the search.

        Parameters
        ----------
        problem : ParameterSynthesisScenario
            Model and parameters to synthesize
        config : SearchConfig, optional
            BoxSearch configuration, by default SearchConfig()

        Returns
        -------
        BoxSearchEpisode
            Final search results (parameter space) and statistics.
        """

        # problem.encode()

        if config.number_of_processes > 1:
            return self._search_mp(problem, config)
        else:
            return self._search_sp(problem, config)

    def _search_sp(self, problem, config: "FUNMANConfig") -> ParameterSpace:
        episode = BoxSearchEpisode(config=config, problem=problem)
        episode._initialize_boxes(config.num_initial_boxes)
        rval = QueueSP()
        all_results = {
            "true_boxes": [],
            "false_boxes": [],
            "true_points": [],
            "false_points": [],
        }
        config._handler.open()
        self._expand(
            rval,
            episode,
            handler=self._run_handler_step,
            all_results=all_results,
        )
        config._handler.close()
        # rval.put(None)

        # all_results = self._run_handler(rval, config)
        # episode._true_boxes = all_results.get("true_boxes")
        # episode.false_boxes = all_results.get("false_boxes")
        # episode._true_points = all_results.get("true_points")
        # episode._false_points = all_results.get("false_points")
        parameter_space = ParameterSpace(
            true_boxes=all_results.get("true_boxes"),
            false_boxes=all_results.get("false_boxes"),
            true_points=all_results.get("true_points"),
            false_points=all_results.get("false_points"),
        )
        return parameter_space

    def _search_mp(self, problem, config: "FUNMANConfig") -> ParameterSpace:
        l = mp.get_logger()
        l.setLevel(LOG_LEVEL)
        processes = config.number_of_processes
        with mp.Manager() as manager:
            rval = manager.Queue()
            episode = BoxSearchEpisodeMP(
                config=config, problem=problem, manager=manager
            )

            expand_count = processes - 1
            episode._initialize_boxes(expand_count)
            idle_mutex = manager.Lock()
            idle_flags = [manager.Event() for _ in range(expand_count)]

            with mp.Pool(processes=processes) as pool:
                more_work_condition = manager.Condition()

                # start the result handler process
                l.info("Starting result handler process")
                rval_handler_process = pool.apply_async(
                    self._run_handler, args=(rval, config)
                )
                # blocking exec of the expansion processes
                l.info(f"Starting {expand_count} expand processes")

                starmap_result = pool.starmap_async(
                    self._expand,
                    [
                        (
                            rval,
                            episode,
                            {
                                "idx": idx,
                                "more_work": more_work_condition,
                                "idle_mutex": idle_mutex,
                                "idle_flags": idle_flags,
                            },
                        )
                        for idx in range(expand_count)
                    ],
                )

                # tell the result handler process we are done with the expansion processes
                try:
                    if config._wait_action is not None:
                        while not starmap_result.ready():
                            config._wait_action.run()
                    starmap_result.wait()
                except KeyboardInterrupt:
                    l.warninging("--- Received Keyboard Interrupt ---")

                rval.put(None)
                l.info("Waiting for result handler process")
                # wait for the result handler to finish
                rval_handler_process.wait(timeout=config.wait_timeout)

                if not rval_handler_process.successful():
                    l.error("Result handler failed to exit")
                all_results = rval_handler_process.get()

                # episode._true_boxes = all_results.get("true_boxes")
                # episode._false_boxes = all_results.get("false_boxes")
                # episode._true_points = all_results.get("true_points")
                # episode._false_points = all_results.get("false_points")
                parameter_space = ParameterSpace(
                    true_boxes=all_results.get("true_boxes"),
                    false_boxes=all_results.get("false_boxes"),
                    true_points=all_results.get("true_points"),
                    false_points=all_results.get("false_points"),
                )
                return parameter_space
