import re
from typing import List
from pydantic import BaseModel, Field

class ScreenplayScene(BaseModel):
    """Structured representation of an individual screenplay scene block."""
    scene_number: int = Field(..., description="Sequential scene index (1-based)")
    heading: str = Field(..., description="Original scene slugline / heading")
    text: str = Field(..., description="Full text content within this scene")
    start_line: int = Field(1, description="Starting 1-indexed line number in original screenplay")
    end_line: int = Field(1, description="Ending 1-indexed line number in original screenplay")

class ScreenplaySceneParser:
    """
    Parser for screenplay text that identifies scene headings (sluglines)
    and segments screenplay text into sequential, numbered scene blocks.
    """

    # Matches sluglines such as:
    # INT. COFFEE SHOP - DAY
    # EXT. STREET - NIGHT
    # SCENE 01 - INT. DOWNTOWN COFFEE SHOP - DAY
    # INT/EXT. CAR - RAIN
    # I/E. DINER - EVENING
    HEADING_PATTERN = re.compile(
        r"^(?:\s*(?:scene\s+\d+[\s\-:]+)|(?:\s*#+\s*))?"
        r"(?:int\.|ext\.|int/ext\.|int\./ext\.|i/e\.|est\.)"
        r"[^\n]*",
        re.IGNORECASE | re.MULTILINE,
    )

    def parse_scenes(self, screenplay_text: str) -> List[ScreenplayScene]:
        """
        Parse screenplay text into sequential scene records.
        If no recognizable scene headings exist, returns the whole text as Scene 1.
        """
        clean_text = screenplay_text or ""
        lines = clean_text.splitlines()

        if not clean_text.strip():
            return []

        # Find all scene headings and their line numbers (1-indexed)
        heading_matches = []
        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if self.HEADING_PATTERN.match(stripped):
                heading_matches.append((line_idx, stripped))

        # Fallback: if no sluglines detected, treat entire text as Scene 1
        if not heading_matches:
            return [
                ScreenplayScene(
                    scene_number=1,
                    heading="SCENE 1",
                    text=clean_text.strip(),
                    start_line=1,
                    end_line=len(lines) if lines else 1,
                )
            ]

        scenes: List[ScreenplayScene] = []
        num_headings = len(heading_matches)

        for i, (line_num, heading) in enumerate(heading_matches):
            scene_number = i + 1
            start_line = line_num

            # End line is the line before next heading, or end of document
            if i + 1 < num_headings:
                next_line_num = heading_matches[i + 1][0]
                end_line = next_line_num - 1
                scene_lines = lines[start_line - 1 : end_line]
            else:
                end_line = len(lines)
                scene_lines = lines[start_line - 1 :]

            scene_body = "\n".join(scene_lines).strip()
            scenes.append(
                ScreenplayScene(
                    scene_number=scene_number,
                    heading=heading,
                    text=scene_body,
                    start_line=start_line,
                    end_line=end_line,
                )
            )

        return scenes

screenplay_scene_parser = ScreenplaySceneParser()
