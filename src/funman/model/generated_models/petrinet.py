# generated by datamodel-codegen:
#   filename:  petrinet_schema.json
#   timestamp: 2023-06-13T18:26:56+00:00

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, AnyUrl, BaseModel, Field, RootModel


class Rate(BaseModel):
    target: Optional[str] = None
    expression: Optional[str] = None
    expression_mathml: Optional[str] = None


class Initial(BaseModel):
    target: Optional[str] = None
    expression: Optional[str] = None
    expression_mathml: Optional[str] = None


class Distribution(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    parameters: Dict[str, Any]


class Grounding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifiers: Dict[str, Any]
    modifiers: Optional[Dict[str, Any]] = None


class Properties(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: Optional[str] = None
    grounding: Optional[Grounding] = None


class Unit(BaseModel):
    model_config = ConfigDict(extra="allow")

    expression: Optional[str] = None
    expression_mathml: Optional[str] = None


class Parameter(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[float] = None
    grounding: Optional[Grounding] = None
    distribution: Optional[Distribution] = None
    units: Optional[Unit] = None


class Time(BaseModel):
    id: str
    units: Optional[Unit] = None


class OdeSemantics(BaseModel):
    rates: Optional[List[Rate]] = None
    initials: Optional[List[Initial]] = None
    parameters: Optional[List[Parameter]] = None
    time: Optional[Time] = None


class State(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    grounding: Optional[Grounding] = None
    units: Optional[Unit] = None


class States(RootModel):
    root: List[State]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class Transition(BaseModel):
    id: str
    input: List[str]
    output: List[str]
    grounding: Optional[Grounding] = None
    properties: Optional[Properties] = None


class Transitions(RootModel):
    root: List[Transition]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]


class TypeSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: States
    transitions: Transitions


class TypingSemantics(BaseModel):
    type_system: Optional[TypeSystem] = Field(
        None,
        description="A Petri net representing the 'type system' that is necessary to align states and transitions across different models during stratification.",
    )
    type_map: Optional[List[List[str]]] = Field(
        None,
        description="A map between the (state and transition) nodes of the model and the (state and transition) nodes of the type system",
    )


class Model1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    states: States
    transitions: Transitions


class Semantics(BaseModel):
    ode: Optional[OdeSemantics] = None
    typing: Optional[TypingSemantics] = Field(
        None,
        description="(Optional) Information for aligning models for stratification",
    )


class Model(BaseModel):
    model_config = ConfigDict(
        extra="allow", populate_by_name=True, protected_namespaces=()
    )

    name: str
    schema_: AnyUrl = Field(..., alias="schema")
    schema_name: Optional[str] = None
    description: str
    model_version: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    model: Model1
    semantics: Optional[Semantics] = Field(
        None,
        description="Information specific to a given semantics (e.g., ODEs) associated with a model.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="(Optional) Information not useful for execution of the model, but that may be useful to some consumer in the future. E.g. creation timestamp or source paper's author.",
    )
