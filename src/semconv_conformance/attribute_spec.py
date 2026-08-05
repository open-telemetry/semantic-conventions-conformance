# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared `AttributeSpec` / `RequirementLevel` types used by domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RequirementLevel(StrEnum):
    REQUIRED = "required"
    CONDITIONALLY_REQUIRED = "conditionally_required"
    RECOMMENDED = "recommended"
    OPT_IN = "opt_in"


@dataclass(frozen=True)
class AttributeSpec:
    label: str
    required: tuple[str, ...]
    conditionally_required: tuple[str, ...]
    recommended: tuple[str, ...]
    opt_in: tuple[str, ...]
    discriminator_attrs: frozenset[str] = frozenset()

    def attrs_for_requirement_level(self, level: RequirementLevel) -> tuple[str, ...]:
        if level is RequirementLevel.REQUIRED:
            return self.required
        if level is RequirementLevel.CONDITIONALLY_REQUIRED:
            return self.conditionally_required
        if level is RequirementLevel.RECOMMENDED:
            return self.recommended
        if level is RequirementLevel.OPT_IN:
            return self.opt_in
        raise KeyError(f"Unknown requirement level: {level}")
