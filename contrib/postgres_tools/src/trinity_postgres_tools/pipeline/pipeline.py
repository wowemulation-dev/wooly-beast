"""
Pipeline orchestrator for MySQL to PostgreSQL conversion.

The pipeline processes SQL through multiple stages:
1. Preprocessing - Remove mysqldump artifacts
2. Splitting - Split into individual statements
3. Classification - Determine DDL/DML/OTHER for routing
4. Transformation - Apply appropriate converters
5. Postprocessing - Final cleanup
6. Assembly - Rejoin statements
"""

from abc import ABC, abstractmethod
from typing import Protocol

from trinity_postgres_tools.pipeline.context import (
    ConversionContext,
    ConversionOptions,
)


class PipelineStage(Protocol):
    """Protocol defining a pipeline stage."""

    @property
    def name(self) -> str:
        """Stage name for logging."""
        ...

    def process(self, ctx: ConversionContext) -> ConversionContext:
        """
        Process the context through this stage.

        Args:
            ctx: Current conversion context

        Returns:
            Updated context (may be same instance, mutated)
        """
        ...


class BasePipelineStage(ABC):
    """Base class for pipeline stages with common functionality."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stage name for logging."""
        pass

    @abstractmethod
    def process(self, ctx: ConversionContext) -> ConversionContext:
        """Process the context through this stage."""
        pass

    def log(self, ctx: ConversionContext, message: str) -> None:
        """Log a message to the context debug log."""
        ctx.log_debug(f"[{self.name}] {message}")


class ConversionPipeline:
    """
    Multi-stage conversion pipeline.

    Orchestrates the flow of SQL through preprocessing, parsing,
    transformation, and postprocessing stages.
    """

    def __init__(self, options: ConversionOptions | None = None) -> None:
        """
        Initialize the pipeline.

        Args:
            options: Conversion options, or defaults if None
        """
        self.options = options or ConversionOptions()
        self._stages: list[PipelineStage] = []

    def add_stage(self, stage: PipelineStage) -> "ConversionPipeline":
        """
        Add a stage to the pipeline.

        Args:
            stage: Stage to add

        Returns:
            Self for method chaining
        """
        self._stages.append(stage)
        return self

    def convert(self, sql: str) -> str:
        """
        Convert MySQL SQL to PostgreSQL.

        Args:
            sql: MySQL SQL content

        Returns:
            PostgreSQL SQL content
        """
        ctx = self._create_context(sql)
        ctx = self._run_stages(ctx)
        return self._assemble_output(ctx)

    def convert_with_context(self, sql: str) -> tuple[str, ConversionContext]:
        """
        Convert MySQL SQL to PostgreSQL and return context.

        Useful for testing and debugging to inspect conversion details.

        Args:
            sql: MySQL SQL content

        Returns:
            Tuple of (converted SQL, context with stats)
        """
        ctx = self._create_context(sql)
        ctx = self._run_stages(ctx)
        return self._assemble_output(ctx), ctx

    def _create_context(self, sql: str) -> ConversionContext:
        """Create initial context from input SQL."""
        ctx = ConversionContext(options=self.options)
        ctx.current_statement = sql
        return ctx

    def _run_stages(self, ctx: ConversionContext) -> ConversionContext:
        """Run all stages in order."""
        for stage in self._stages:
            ctx.log_debug(f"Entering stage: {stage.name}")
            try:
                ctx = stage.process(ctx)
            except Exception as e:
                ctx.stats.record_error(f"Stage {stage.name} failed: {e!s}")
                if self.options.strict_mode:
                    raise
        return ctx

    def _assemble_output(self, ctx: ConversionContext) -> str:
        """Assemble final output from context."""
        # Join statements with semicolons and newlines
        statements = [s for s in ctx.output_statements if s.strip()]
        if not statements:
            return ""

        # Ensure each statement ends with semicolon
        result = []
        for stmt in statements:
            cleaned = stmt.rstrip()
            if not cleaned.endswith(";"):
                cleaned += ";"
            result.append(cleaned)

        return "\n".join(result) + "\n"


class PipelineBuilder:
    """Builder for constructing conversion pipelines."""

    def __init__(self) -> None:
        self._options = ConversionOptions()
        self._stages: list[PipelineStage] = []

    def with_options(self, options: ConversionOptions) -> "PipelineBuilder":
        """Set conversion options."""
        self._options = options
        return self

    def add_stage(self, stage: PipelineStage) -> "PipelineBuilder":
        """Add a processing stage."""
        self._stages.append(stage)
        return self

    def add_preprocessing(self) -> "PipelineBuilder":
        """Add standard preprocessing stage."""
        # Will be implemented with actual PreprocessingStage
        return self

    def add_splitting(self) -> "PipelineBuilder":
        """Add statement splitting stage."""
        # Will be implemented with actual SplittingStage
        return self

    def add_transformation(self) -> "PipelineBuilder":
        """Add transformation stage."""
        # Will be implemented with actual TransformationStage
        return self

    def add_postprocessing(self) -> "PipelineBuilder":
        """Add postprocessing stage."""
        # Will be implemented with actual PostprocessingStage
        return self

    def build(self) -> ConversionPipeline:
        """Build the configured pipeline."""
        pipeline = ConversionPipeline(self._options)
        for stage in self._stages:
            pipeline.add_stage(stage)
        return pipeline


def create_default_pipeline(options: ConversionOptions | None = None) -> ConversionPipeline:
    """
    Create a pipeline with standard stages.

    This is the main entry point for creating a conversion pipeline
    with all standard processing stages configured.

    Args:
        options: Conversion options, or defaults if None

    Returns:
        Configured conversion pipeline
    """
    # Import here to avoid circular imports
    from trinity_postgres_tools.pipeline.stages import (  # noqa: PLC0415
        PostprocessingStage,
        PreprocessingStage,
        SplittingStage,
        TransformationStage,
    )

    pipeline = ConversionPipeline(options)
    pipeline.add_stage(PreprocessingStage())
    pipeline.add_stage(SplittingStage())
    pipeline.add_stage(TransformationStage())
    pipeline.add_stage(PostprocessingStage())

    return pipeline
