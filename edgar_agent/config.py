import os
from dataclasses import dataclass


@dataclass
class ResearchConfiguration:

    # gemini_model: str = "gemini-flash-latest"
    gemini_model: str = "gemini-2.5-flash"


config = ResearchConfiguration()