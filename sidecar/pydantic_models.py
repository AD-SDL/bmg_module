"""Request bodies for the BMG sidecar HTTP API."""

from typing import Optional

from pydantic import BaseModel, Field


class SetTempRequest(BaseModel):
    """Body for POST /set_temp."""

    temp: float = Field(
        ...,
        description=(
            "Temperature in Celsius. Valid values: 0.0 (off), 0.1 (monitor only), "
            "25.0-45.0 standard, or 10.0-60.0 for extended-temperature-range models."
        ),
    )


class RunAssayRequest(BaseModel):
    """Body for POST /run_assay."""

    assay_name: str = Field(
        ..., description="Protocol name as defined in SMART Control."
    )
    protocol_database_path: str = Field(
        ..., description="Path to the BMG protocol database directory."
    )
    data_output_directory_path: str = Field(
        ..., description="Path to the output directory (must exist)."
    )
    data_output_file_name: Optional[str] = Field(
        default=None,
        description="Output file name; defaults to <unix_timestamp>.txt if omitted.",
    )
    plate_id1: int = Field(default=1)
    plate_id2: int = Field(default=2)
    plate_id3: int = Field(default=3)
