from typing import List
from funman.plotting import BoxPlotter
from funman.search_episode import SearchEpisode
from funman.search_utils import Box
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class ParameterSpace(object):
    def __init__(self, true_boxes: List[Box], false_boxes: List[Box]) -> None:
        self.true_boxes = true_boxes
        self.false_boxes = false_boxes

    # STUB project parameter space onto a parameter
    @staticmethod
    def project() -> "ParameterSpace":
        raise NotImplementedError()
        return ParameterSpace()

    @staticmethod
    def _intersect_boxes(b1s, b2s):
        results_list = []
        for box1 in b1s:
            for box2 in b2s:
                subresult = Box.intersect_two_boxes(box1, box2)
                if subresult != None:
                    results_list.append(subresult)
        return results_list

    # STUB intersect parameters spaces
    @staticmethod
    def intersect(ps1, ps2):
        return ParameterSpace(
            ParameterSpace._intersect_boxes(ps1.true_boxes, ps2.true_boxes), 
            ParameterSpace._intersect_boxes(ps1.false_boxes, ps2.false_boxes) 
        )

    
    @staticmethod
    def symmetric_difference(ps1: "ParameterSpace", ps2: "ParameterSpace"):
        return ParameterSpace(
            ParameterSpace._symmetric_difference(ps1.true_boxes, ps2.true_boxes), 
            ParameterSpace._symmetric_difference(ps1.false_boxes, ps2.false_boxes) 
        )

    @staticmethod
    def _symmetric_difference(ps1: List[Box], ps2: List[Box]) -> List[Box]:
        results_list = []

        for box2 in ps2:
            box2_results = []
            should_extend = True
            for box1 in ps1:
                subresult = Box.symmetric_difference_two_boxes(box2, box1)
                if subresult != None:
                    box2_results.extend(subresult)
                else:
                    should_extend = False
                    break
            if should_extend:
                results_list.extend(box2_results)

        for box1 in ps1:
            box1_results = []
            should_extend = True
            for box2 in ps2:
                subresult = Box.symmetric_difference_two_boxes(box1, box2)
                if subresult != None:
                    box1_results.extend(subresult)
                else:
                    should_extend = False
                    break
            if should_extend:
                results_list.extend(box1_results)

        return results_list
    
    # STUB construct space where all parameters are equal
    @staticmethod
    def construct_all_equal(ps) -> "ParameterSpace":
        raise NotImplementedError()
        return ParameterSpace()

    # STUB compare parameter spaces for equality
    @staticmethod
    def compare(ps1, ps2) -> bool:
        raise NotImplementedError()
        raise NotImplementedError()

    
    def plot(self, color="b",alpha=0.2):
        custom_lines = [
            Line2D([0], [0], color='g', lw=4,alpha=alpha),
            Line2D([0], [0], color='r', lw=4,alpha=alpha),
        ]
        
        plt.legend(custom_lines, ["true", "false"])
        for b1 in self.true_boxes:
            BoxPlotter.plot2DBoxList(b1, color='g')    
        for b1 in self.false_boxes:
            BoxPlotter.plot2DBoxList(b1, color='r')      
        # plt.show(block=True) 
        pass
