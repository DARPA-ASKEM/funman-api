import copy
import logging
from decimal import ROUND_CEILING, Decimal
from pickle import FALSE
from statistics import mean as average
from typing import Dict, List, Literal, Optional, Union

from numpy import nextafter
from pydantic import BaseModel, Field

import funman.utils.math_utils as math_utils
from funman.constants import LABEL_FALSE, LABEL_TRUE, LABEL_UNKNOWN, Label

from . import EncodingSchedule, Interval, Point, Timestep
from .explanation import BoxExplanation
from .interval import Interval
from .parameter import ModelParameter, Parameter
from .symbol import ModelSymbol

l = logging.getLogger(__name__)


# @total_ordering
class Box(BaseModel):
    """
    A Box maps n parameters to intervals, representing an n-dimensional connected open subset of R^n.
    """

    type: Literal["box"] = "box"
    label: Label = LABEL_UNKNOWN
    bounds: Dict[str, Interval] = {}
    explanation: Optional[BoxExplanation] = None
    schedule: Optional[EncodingSchedule] = None
    corner_points: List[Point] = []
    points: List[Point] = []
    _points_at_step: Dict[Timestep, List[Point]] = {}

    @staticmethod
    def from_point(point: Point) -> "Box":
        box = Box()
        box.bounds = {
            p: Interval.from_value(v) for p, v in point.values.items()
        }
        box.points.append(point)
        box.schedule = point.schedule
        box.label = point.label
        return box

    def add_point(self, point: Point) -> None:
        if point not in self.points:
            timestep = point.timestep()
            step_points = self._points_at_step.get(timestep, [])
            step_points.append(point)
            self._points_at_step[timestep] = step_points
            self.points.append(point)

    def true_points(self, step=None) -> List[Point]:
        return [
            p
            for p in self.points
            if p.label == LABEL_TRUE and (step is None or p.timestep() == step)
        ]

    def false_points(self, step=None) -> List[Point]:
        return [
            p
            for p in self.points
            if p.label == LABEL_FALSE
            and (step is None or p.timestep() == step)
        ]

    def explain(self) -> "BoxExplanation":
        expl = {"box": {k: v.model_dump() for k, v in self.bounds.items()}}
        expl.update(self.explanation.explain())
        return expl

    def timestep(self) -> Interval:
        return self.bounds["timestep"]

    def __hash__(self):
        return int(sum([i.__hash__() for _, i in self.bounds.items()]))

    def advance(self):
        # Advancing a box means that we move the time step forward until it exhausts the possible number of steps
        if self.timestep().lb == self.timestep().ub:
            return None
        else:
            box: Box = self.model_copy(deep=True)
            box.timestep().lb += 1
            # Remove points because they correspond to prior timesteps
            box.points = [
                pt
                for pt in self.points
                if box.timestep().contains_value(pt.timestep())
            ]
            box._points_at_step = {
                step: [p for p in pts if p in box.points]
                for step, pts in box._points_at_step.items()
            }
            return box

    def corners(self, parameters: List[Parameter] = None) -> List[Point]:
        points: List[Point] = [Point(values={})]
        parameter_names = (
            [p.name for p in parameters] if parameters is not None else []
        )
        for p, interval in self.bounds.items():
            if p not in parameter_names:
                continue
            if interval.is_point():
                for pt in points:
                    pt.values[p] = interval.lb
            else:
                lb_points = [pt.model_copy(deep=True) for pt in points]
                ub_points = [pt.model_copy(deep=True) for pt in points]

                nextbefore_ub = (
                    interval.ub
                    if interval.closed_upper_bound
                    else float(nextafter(interval.ub, interval.lb))
                )

                for pt in lb_points:
                    pt.values[p] = interval.lb
                for pt in ub_points:
                    pt.values[p] = nextbefore_ub
                points = lb_points + ub_points
        return points

    def current_step(self) -> "Box":
        # Restrict bounds on num_steps to the lower bound (i.e., the current step)
        curr = self.model_copy(deep=True)
        timestep = curr.timestep()
        timestep.closed_upper_bound = True
        timestep.ub = timestep.lb

        return curr

    def project(self, vars: Union[List[ModelParameter], List[str]]) -> "Box":
        """
        Takes a subset of selected variables (vars_list) of a given box (b) and returns another box that is given by b's values for only the selected variables.

        Parameters
        ----------
        vars : Union[List[ModelParameter], List[str]]
            variables to project onto

        Returns
        -------
        Box
            projected box

        """
        bp = copy.deepcopy(self)
        if len(vars) > 0:
            if isinstance(vars[0], str):
                bp.bounds = {k: v for k, v in bp.bounds.items() if k in vars}
            elif isinstance(vars[0], ModelParameter):
                vars_str = [v.name for v in vars]
                bp.bounds = {
                    k: v for k, v in bp.bounds.items() if k in vars_str
                }
            else:
                raise Exception(
                    f"Unknown type {type(vars[0])} used as intput to Box.project()"
                )
        else:
            bp.bounds = {}
        return bp

    def _merge(self, other: "Box") -> "Box":
        """
        Merge two boxes.  This function assumes the boxes meet in one dimension and are equal in all others.

        Parameters
        ----------
        other : Box
            other box

        Returns
        -------
        Box
            merge of two boxes that meet in one dimension
        """
        bounds = {p: None for p in self.bounds.keys()}
        for p in bounds:
            if self.bounds[p].meets(other.bounds[p]):
                bounds[p] = Interval(
                    lb=min(self.bounds[p].lb, other.bounds[p].lb),
                    ub=max(self.bounds[p].ub, other.bounds[p].ub),
                )
            else:
                bounds[p] = Interval(
                    lb=self.bounds[p].lb, ub=self.bounds[p].ub
                )

        merged = self.model_copy(deep=True)
        merged.bounds = bounds
        return merged

    def _get_merge_candidates(self, boxes: Dict[ModelParameter, List["Box"]]):
        equals_set = set([])
        meets_set = set([])
        disqualified_set = set([])
        for p in boxes:
            sorted = boxes[p]
            # find boxes in sorted that meet or equal self in dimension p
            self_index = sorted.index(self)
            # sorted is sorted by upper bound, and candidate boxes are either
            # before or after self in the list
            # search backward
            for r in [
                reversed(range(self_index)),  # search forward
                range(self_index + 1, len(boxes[p])),  # search backward
            ]:
                for i in r:
                    if sorted[i] == self:
                        continue

                    if (
                        sorted[i].bounds[p].meets(self.bounds[p])
                        and sorted[i] not in disqualified_set
                        and sorted[i].schedule == self.schedule
                    ):
                        if sorted[i] in meets_set:
                            # Need exactly one dimension where they meet, so disqualified
                            meets_set.remove(sorted[i])
                            disqualified_set.add(sorted[i])
                        else:
                            meets_set.add(sorted[i])
                    elif (
                        sorted[i].bounds[p] == self.bounds[p]
                        and sorted[i] not in disqualified_set
                        and sorted[i].schedule == self.schedule
                    ):
                        equals_set.add(sorted[i])
                    else:
                        if sorted[i] in meets_set:
                            meets_set.remove(sorted[i])
                        if sorted[i] in equals_set:
                            equals_set.remove(sorted[i])
                        disqualified_set.add(sorted[i])
                    if sorted[i].bounds[p].disjoint(
                        self.bounds[p]
                    ) and not sorted[i].bounds[p].meets(self.bounds[p]):
                        break  # Because sorted, no further checking needed
        if len(boxes.keys()) == 1:  # 1D
            candidates = meets_set
        else:  # > 1D
            candidates = meets_set.intersection(equals_set)
        return candidates

    def _copy(self):
        c = Box(
            bounds={
                p: Interval(lb=b.lb, ub=b.ub) for p, b in self.bounds.items()
            }
        )
        return c

    def __lt__(self, other):
        if isinstance(other, Box):
            # prefer boxes with true points
            # prefer boxes later in time
            # prefer boxes with smaller width
            s_t = len(self.true_points())
            o_t = len(other.true_points())
            if s_t == o_t:
                if self.timestep().lb == other.timestep().lb:
                    return self.normalized_width() > other.normalized_width()
                else:
                    return self.timestep().lb > other.timestep().lb
            else:
                return s_t > o_t
        else:
            raise Exception(f"Cannot compare __lt__() Box to {type(other)}")

    def __eq__(self, other):
        if isinstance(other, Box):
            return all(
                [self.bounds[p] == other.bounds[p] for p in self.bounds.keys()]
            )
        else:
            return False

    def __repr__(self):
        return str(self.model_dump())

    def __str__(self):
        bounds_str = "\n".join(
            [
                f"{k}:\t{str(v)}\t({v.normalized_width():.5f})"
                for k, v in self.bounds.items()
            ]
        )
        box_str = f"Box(\n|+pts|: {len(self.true_points())}\n|-pts|: {len(self.false_points())}\nlabel: {self.label}\nwidth: {self.width()},\ntimepoints: {Interval(lb=self.schedule.time_at_step(int(self.timestep().lb)), ub=self.schedule.time_at_step(int(self.timestep().ub)), closed_upper_bound=True)},\n{bounds_str}\n)"
        return box_str
        # return f"Box(t_{self.timestep()}={Interval(lb=self.schedule.time_at_step(int(self.timestep().lb)), ub=self.schedule.time_at_step(int(self.timestep().ub)), closed_upper_bound=True)} {self.bounds}), width = {self.width()}"

    def finite(self) -> bool:
        """
        Are all parameter intervals finite?

        Returns
        -------
        bool
            all parameter intervals are finite
        """
        return all([i.finite() for _, i in self.bounds.items()])

    def contains(self, other: "Box") -> bool:
        """
        Does the interval for each parameter in self contain the interval for the corresponding parameter in other?

        Parameters
        ----------
        other : Box
            other box

        Returns
        -------
        bool
            self contains other
        """
        return all(
            [
                interval.contains(other.bounds[p])
                for p, interval in self.bounds.items()
            ]
        )

    def contains_point(self, point: Point) -> bool:
        """
        Does the box contain a point?

        Parameters
        ----------
        point : Point
            a point

        Returns
        -------
        bool
            the box contains the point
        """
        return all(
            [
                interval.contains_value(point.values[p])
                for p, interval in self.bounds.items()
            ]
        )

    def equal(
        self, b2: "Box", param_list: List[str] = None
    ) -> bool:  ## added 11/27/22 DMI
        ## FIXME @dmosaphir use Parameter instead of str for param_list
        """
        Are two boxes equal, considering only parameters in param_list?

        Parameters
        ----------
        b1 : Box
            box 1
        b2 : Box
            box 2
        param_list : list
            parameters over which to restrict the comparison

        Returns
        -------
        bool
            boxes are equal
        """

        if param_list:
            result = []
            for p1 in param_list:
                for b in self.bounds:
                    if b.name == p1:
                        b1_bounds = [b.lb, b.ub]
                for b in b2.bounds:
                    if b.name == p1:
                        b2_bounds = [b.lb, b.ub]
                if b1_bounds == b2_bounds:
                    result.append(True)
                else:
                    result.append(False)
            return all(result)
        else:
            return self == b

    def intersects(self, other: "Box") -> bool:
        """
        Does self and other intersect? I.e., do all parameter intervals instersect?

        Parameters
        ----------
        other : Box
            other box

        Returns
        -------
        bool
            self intersects other
        """
        return all(
            [
                interval.intersects(other.bounds[p])
                for p, interval in self.bounds.items()
            ]
        )

    def _get_max_width_point_Parameter(
        self, points: List[List[Point]], parameters: List[Parameter]
    ):
        """
        Get the parameter that has the maximum average distance from the center point for each parameter and the value for the parameter assigned by each point.

        Parameters
        ----------
        points : List[Point]
            Points in the box

        Returns
        -------
        Parameter
            parameter (dimension of box) where points are most distant from the center of the box.
        """
        parameter_names = [p.name for p in parameters]
        group_centers = {
            p: [average([pt.values[p] for pt in grp]) for grp in points]
            for p in self.bounds
            if p in parameter_names
        }
        centers = {p: average(grp) for p, grp in group_centers.items()}
        # print(points)
        # print(centers)
        point_distances = [
            {
                p: Decimal(abs(pt.values[p] - centers[p]))
                for p in pt.values
                if p in centers
            }
            for grp in points
            for pt in grp
        ]

        parameter_widths = {
            p: average([pt[p] for pt in point_distances])
            for p in self.bounds
            if p in parameter_names
        }
        parameter_widths = {
            p: (
                v / self.bounds[p].original_width
                if self.bounds[p].original_width > 0.0
                else 0.0
            )
            for p, v in parameter_widths.items()
        }

        # normalized_parameter_widths = {
        #     p: average([pt[p] for pt in point_distances])
        #     / (self.bounds[p].width())
        #     for p in self.bounds
        #     if self.bounds[p].width() > 0
        # }
        max_width_parameter = max(
            parameter_widths, key=lambda k: parameter_widths[k]
        )
        if parameter_widths[max_width_parameter] == 0.0:
            return None
        else:
            return max_width_parameter

    def _get_max_width_Parameter(
        self, normalize=False, parameters: List[ModelParameter] = None
    ) -> Union[str, ModelSymbol]:
        if parameters:
            widths = {
                parameter.name: (
                    self.bounds[parameter.name].width(normalize=normalize)
                )
                for parameter in parameters
            }
        else:
            widths = {
                p: self.bounds[p].width(normalize=normalize)
                for p in self.bounds
            }
        if "timestep" in widths:
            del widths["timestep"]
        max_width = max(widths, key=widths.get)

        return max_width

    def _get_min_width_Parameter(
        self, normalize=FALSE, parameters: List[ModelParameter] = None
    ) -> Union[str, ModelSymbol]:
        if parameters:
            widths = {
                parameter.name: (
                    self.bounds[parameter.name].width(normalize=normalize)
                )
                for parameter in parameters
            }
        else:
            widths = {
                p: (self.bounds[p].width(normalize=normalize))
                for p in self.bounds
            }
        min_width = min(widths, key=widths.get)

        return min_width

    def volume(
        self,
        normalize=False,
        parameters: List[ModelParameter] = None,
        *,
        ignore_zero_width_dimensions=True,
    ) -> Decimal:
        # construct a list of parameter names to consider
        # if no parameters are requested then use all of the bounds
        if parameters is None:
            pnames = list(self.bounds.keys())
        else:
            pnames = [
                p.name if isinstance(p.name, str) else p.name.name
                for p in parameters
                if isinstance(p, ModelParameter)
            ]

        # handle the volume of zero dimensions
        if len(pnames) <= 0:
            return Decimal("nan")

        # get a mapping of parameters to widths
        # use normalize.get(p.name, None) to select between default behavior and normalization
        widths = {p: self.bounds[p].width(normalize=normalize) for p in pnames}
        if ignore_zero_width_dimensions:
            # filter widths of zero from the
            widths = {p: w for p, w in widths.items() if w != 0.0}

        # TODO in there a 'class' of parameters that we can identify
        # that need this same treatment. Specifically looking for
        # strings 'num_steps' and 'step_size' is brittle.
        num_timepoints = 1
        if self.schedule:
            num_timepoints = Decimal(
                int(self.timestep().ub) + 1 - int(self.timestep().lb)
            ).to_integral_exact(rounding=ROUND_CEILING)
            if normalize is not None:
                num_timepoints = num_timepoints / Decimal(
                    len(self.schedule.timepoints)
                )
        elif "num_steps" in widths:
            del widths["num_steps"]
            # TODO this timepoint computation could use more thought
            # for the moment it just takes the ceil(width) + 1.0
            # so num steps 1.0 to 2.5 would result in:
            # ceil(2.5 - 1.0) + 1.0 = 3.0
            num_timepoints = Decimal(
                self.bounds["num_steps"].ub
            ).to_integral_exact(rounding=ROUND_CEILING)
            num_timepoints += 1

        if "step_size" in widths:
            del widths["step_size"]

        if len(widths) <= 0:
            # TODO handle volume of a point
            return Decimal(0.0)

        # compute product
        product = Decimal(1.0)
        for param_width in widths.values():
            if param_width < 0:
                raise Exception("Negative parameter width")
            product *= Decimal(param_width)
        product *= num_timepoints
        return product

    def normalized_width(self, parameters: List[ModelParameter] = None):
        p = self._get_max_width_Parameter(
            normalize=True, parameters=parameters
        )
        norm_width = self.bounds[p].normalized_width()
        return norm_width

    def width(
        self,
        normalize=False,
        parameters: List[ModelParameter] = None,
    ) -> float:
        """
        The width of a box is the maximum width of a parameter interval.

        Returns
        -------
        float
            Max{p: parameter}(p.ub-p.lb)
        """
        if normalize:
            return self.normalized_width(parameters=parameters)
        else:
            p = self._get_max_width_Parameter(
                normalize=normalize, parameters=parameters
            )
            return self.bounds[p].width(normalize=normalize)

    def variance(self, overwrite_cache=False) -> float:
        """
        The variance of a box is the maximum variance of a parameter interval.
        STUB for Milestone 8 sensitivity analysis

        Returns
        -------
        float
            Variance{p: parameter}
        """
        pass

    def split(
        self,
        points: List[List[Point]] = None,
        normalize: Dict[str, float] = {},
        parameters=[],
    ):
        """
        Split box along max width dimension. If points are provided, then pick the axis where the points are maximally distant.

        Parameters
        ----------
        points : List[Point], optional
            solution points that the split will separate, by default None

        Returns
        -------
        List[Box]
            Boxes resulting from the split.
        """
        p = None
        if points:
            p = self._get_max_width_point_Parameter(
                points, parameters=parameters
            )
            if (
                p is not None
                and self.bounds[p].normalized_width()
                < Decimal(0.5) * self.normalized_width()
            ):
                # Discard selected parameter if its width is much smaller than box width
                p = None
            if p is not None:
                mid = self.bounds[p].midpoint(
                    points=[[pt.values[p] for pt in grp] for grp in points]
                )
                if mid == self.bounds[p].lb or mid == self.bounds[p].ub:
                    # Fall back to box midpoint if point-based mid is degenerate
                    p = self._get_max_width_Parameter(parameter=parameters)
                    mid = self.bounds[p].midpoint()

        if p is None:
            p = self._get_max_width_Parameter(
                normalize=normalize, parameters=parameters
            )
            mid = self.bounds[p].midpoint()

        b1 = self.model_copy(deep=True)
        b2 = self.model_copy(deep=True)

        # b1 is lower half
        assert math_utils.lte(b1.bounds[p].lb, mid)
        b1.bounds[p] = Interval(lb=b1.bounds[p].lb, ub=mid)
        b1.bounds[p].original_width = self.bounds[p].original_width
        b1.points = [pt for pt in b1.points if b1.contains_point(pt)]
        b1._points_at_step = {
            step: [p for p in pts if p in b1.points]
            for step, pts in b1._points_at_step.items()
        }

        # b2 is upper half
        assert math_utils.lte(mid, b2.bounds[p].ub)
        b2.bounds[p] = Interval(lb=mid, ub=b2.bounds[p].ub)
        b2.bounds[p].original_width = self.bounds[p].original_width
        b2.points = [pt for pt in b2.points if b2.contains_point(pt)]
        b2._points_at_step = {
            step: [p for p in pts if p in b2.points]
            for step, pts in b2._points_at_step.items()
        }

        l.info(
            f"Split({p}[{self.bounds[p].lb, mid}][{mid, self.bounds[p].ub}])"
        )
        l.info(
            f"widths: {self.width():.5f} -> {b1.width():.5f} {b2.width():.5f} (raw), {self.normalized_width():.5f} -> {b1.normalized_width():.5f} {b2.normalized_width():.5f} (norm)"
        )
        return [b2, b1]

    def intersect(self, b2: "Box", param_list: List[str] = None):
        """
        Intersect self with box, optionally over only a subset of the dimensions listed in param_list.

        Parameters
        ----------
        b2 : Box
            box to intersect with
        param_list : List[str], optional
            parameters to intersect, by default None

        Returns
        -------
        Box
            box representing intersection, optionally defined over parameters in param_list (when specified)
        """
        params_ans = []
        common_params = (
            param_list if param_list else [k.name for k in self.bounds]
        )
        for p1 in common_params:
            # FIXME iterating over dict keys is not efficient
            for b, i in self.bounds.items():
                if b == p1:
                    b1_bounds = Interval(lb=i.lb, ub=i.ub)
            for b, i in b2.bounds.items():
                if b == p1:
                    b2_bounds = Interval(lb=i.lb, ub=i.ub)
            intersection_ans = b1_bounds.intersection(
                b2_bounds
            )  ## will be a list with 2 elements (lower and upper bound) or empty list
            if (
                len(intersection_ans) < 1
            ):  ## empty list: no intersection in 1 variable means no intersection overall.
                return None
            else:
                new_param = ModelParameter(
                    name=f"{p1}",
                    interval=Interval(
                        lb=intersection_ans[0], ub=intersection_ans[1]
                    ),
                )
                params_ans.append(new_param)
        return Box(
            bounds={
                p.name: Interval(lb=p.interval.lb, ub=p.interval.ub)
                for p in params_ans
            }
        )

    def symm_diff(b1: "Box", b2: "Box"):
        result = []
        ## First check that the two boxes have the same variables
        vars_b1 = set([b for b in b1.bounds])
        vars_b2 = set([b for b in b2.bounds])
        if vars_b1 == vars_b2:
            vars_list = list(vars_b1)
            print("symm diff in progress")
        else:
            print(
                "cannot take the symmetric difference of two boxes that do not have the same variables."
            )
            raise Exception(
                "Cannot take symmetric difference since the two boxes do not have the same variables"
            )
        ### Find intersection
        desired_vars_list = list(vars_b1)
        intersection = b1.intersect(b2, param_list=desired_vars_list)
        ### Calculate symmetric difference based on intersection
        if (
            intersection == None
        ):  ## No intersection, so symmetric difference is just the original boxes
            return [b1, b2]
        else:  ## Calculate symmetric difference
            unknown_boxes = [b1, b2]
            false_boxes = []
            true_boxes = []
            while len(unknown_boxes) > 0:
                b = unknown_boxes.pop()
                if Box.contains(intersection, b) == True:
                    false_boxes.append(b)
                elif Box.contains(b, intersection) == True:
                    new_boxes = Box.split(b)
                    for i in range(len(new_boxes)):
                        unknown_boxes.append(new_boxes[i])
                else:
                    true_boxes.append(b)
            return true_boxes

    def __intersect_two_boxes(b1, b2):
        # FIXME subsumed by Box.intersect(), can be removed.
        a = list(b1.bounds.values())
        b = list(b2.bounds.values())
        result = []
        d = len(a)  ## dimension
        for i in range(d):
            subresult = a[i].intersection(b[i])
            if subresult == []:
                return None
            else:
                result.append(subresult)
        return result

    @staticmethod
    def _subtract_two_1d_boxes(a, b):
        """Given 2 intervals a = [a0,a1] and b=[b0,b1], return the part of a that does not intersect with b."""
        if intersect_two_1d_boxes(a, b) == None:
            return a
        else:
            if a.lb == b.lb:
                if math_utils.lt(a.ub, b.ub):
                    minArray = a
                    maxArray = b
                else:
                    minArray = b
                    maxArray = a
            elif math_utils.lt(a.lb, b.lb):
                minArray = a
                maxArray = b
            else:
                minArray = b
                maxArray = a
            if math_utils.gt(
                minArray.ub, maxArray.lb
            ):  ## has nonempty intersection. return intersection
                return [float(maxArray.lb), float(minArray.ub)]
            else:  ## no intersection.
                return []

        return [lhs, rhs]

    @staticmethod
    def __intersect_two_boxes(a: "Box", b: "Box"):
        # FIXME not sure how this is different than Box.intersect()
        a_params = list(a.bounds.keys())
        b_params = list(b.bounds.keys())

        beta_0_a = a.bounds[a_params[0]]
        beta_1_a = a.bounds[a_params[1]]
        beta_0_b = b.bounds[b_params[0]]
        beta_1_b = b.bounds[b_params[1]]

        beta_0 = beta_0_a.intersection(beta_0_b)
        if len(beta_0) < 1:
            return None
        beta_1 = beta_1_a.intersection(beta_1_b)
        if len(beta_1) < 1:
            return None

        return Box(
            bounds={
                ModelParameter(
                    name=a_params[0], lb=beta_0[0], ub=beta_0[1]
                ): Interval(lb=beta_0[0], ub=beta_0[1]),
                ModelParameter(
                    name=a_params[1], lb=beta_1[0], ub=beta_1[1]
                ): Interval(lb=beta_1[0], ub=beta_1[1]),
            }
        )

    ### Can remove and replace this with Box.symm_diff, which works for any number of dimensions.  TODO write a corresponding parameter space symmetric difference and use case.
    def _symmetric_difference_two_boxes(self, b: "Box") -> List["Box"]:
        result: List["Box"] = []
        # if the same box then no symmetric difference
        if self == b:
            return result

        ## no intersection so they are disjoint - return both original boxes
        if Box.__intersect_two_boxes(self, b) == None:
            return [self, b]

        # There must be some symmetric difference below here
        a_params = list(self.bounds.keys())
        b_params = list(b.bounds.keys())

        beta_0_a = self.bounds[a_params[0]]
        beta_1_a = self.bounds[a_params[1]]
        beta_0_b = b.bounds[b_params[0]]
        beta_1_b = b.bounds[b_params[1]]

        # TODO assumes 2 dimensions and aligned parameter names
        def make_box_2d(p_bounds):
            b0_bounds = p_bounds[0]
            b1_bounds = p_bounds[1]
            b = Box(
                bounds={
                    ModelParameter(
                        name=a_params[0], lb=b0_bounds.lb, ub=b0_bounds.ub
                    ): Interval(lb=b0_bounds.lb, ub=b0_bounds.ub),
                    ModelParameter(
                        name=a_params[1], lb=b1_bounds.lb, ub=b1_bounds.ub
                    ): Interval(lb=b1_bounds.lb, ub=b1_bounds.ub),
                }
            )
            return b

        xbounds = Box._subtract_two_1d_intervals(beta_0_a, beta_0_b)
        if xbounds != None:
            result.append(make_box_2d([xbounds, beta_1_a]))
        xbounds = Box._subtract_two_1d_intervals(beta_0_b, beta_0_a)
        if xbounds != None:
            result.append(make_box_2d([xbounds, beta_1_b]))
        ybounds = Box._subtract_two_1d_intervals(beta_1_a, beta_1_b)
        if ybounds != None:
            result.append(make_box_2d([beta_0_a, ybounds]))
        ybounds = Box._subtract_two_1d_intervals(beta_1_b, beta_1_a)
        if ybounds != None:
            result.append(make_box_2d([beta_0_b, ybounds]))

        return result
