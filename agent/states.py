"""
states.py — Guided Component Architect
========================================
Pydantic models for the Angular component generation pipeline.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AngularComponent(BaseModel):
    """
    Represents a fully generated Angular component with all three source files.
    Tracks validation state and retry count so the pipeline can self-correct.
    """
    component_name: str = Field(
        description="PascalCase component name, e.g. LoginCardComponent"
    )
    typescript_code: str = Field(
        description="Full Angular TypeScript file content (.component.ts)"
    )
    html_template: str = Field(
        description="Full Angular HTML template content (.component.html)"
    )
    scss_styles: str = Field(
        description="Component SCSS styles (.component.scss)"
    )
    validation_passed: bool = Field(False, description="True if all validation checks passed")
    validation_errors: list[str] = Field(
        default_factory=list,
        description="List of validation error messages"
    )
    retry_count: int = Field(
        0,
        description="Number of generation attempts so far (used to enforce MAX_RETRIES)"
    )


class ComponentRequest(BaseModel):
    """
    Top-level state object threaded through the entire pipeline:
    generator → validator → corrector → finalizer.
    """
    user_prompt: str = Field(
        description="Natural-language description of the Angular component to generate"
    )
    conversation_history: list[dict] = Field(
        default_factory=list,
        description="Multi-turn chat history for context-aware regeneration"
    )
    current_component: Optional[AngularComponent] = Field(
        None,
        description="Most recently generated component (may have validation errors)"
    )
    final_component: Optional[AngularComponent] = Field(
        None,
        description="Validated (or best-effort) component after the pipeline finishes"
    )
    status: str = Field(
        "pending",
        description="Pipeline status: 'pending' while running, 'DONE' when finalized"
    )