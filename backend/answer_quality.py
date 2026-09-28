"""Small deterministic guard for citations in generated statistical claims."""

import re


SOURCE_PATTERN = re.compile(r"\[Source: ([^\]]+)\]")
AVERAGE_PATTERN = re.compile(
    r"(?P<season>20\d{2}-\d{2}) regular season, last (?P<count>\d+) games .*?"
    r"averaging (?P<points>\d+(?:\.\d+)?) pts, (?P<rebounds>\d+(?:\.\d+)?) reb, "
    r"(?P<assists>\d+(?:\.\d+)?) ast"
)


def uncited_stat_paragraphs(answer: str) -> bool:
    """A numeric paragraph with no citation cannot be shown as grounded analysis."""
    for paragraph in re.split(r"\n\s*\n", answer):
        plain = SOURCE_PATTERN.sub("", paragraph)
        if re.search(r"\d", plain) and not SOURCE_PATTERN.search(paragraph):
            return True
    return False


def sourced_fallback(sources: list) -> str | None:
    """Explain direct game-log sources when generated citation placement fails."""
    if not sources:
        return None
    if sources[0].id.startswith("nba_ppg_leaders_"):
        match = re.search(r"#1 (.+?): (\d+(?:\.\d+)?) PPG in (\d+) games", sources[0].content)
        season = re.search(r"NBA (20\d{2}-\d{2})", sources[0].content)
        if match and season:
            return (f"{match[1]} leads the NBA in {season[1]} regular-season scoring "
                    f"at {match[2]} points per game across {match[3]} games. "
                    f"[Source: {sources[0].id}]")
        return None
    paragraphs = []
    for source in sources:
        match = AVERAGE_PATTERN.search(source.content)
        if not match:
            return None
        paragraphs.append(
            f"{source.player} averaged {match['points']} points, {match['rebounds']} rebounds, "
            f"and {match['assists']} assists over their last {match['count']} "
            f"{match['season']} regular-season games. [Source: {source.id}]"
        )
    return "\n\n".join(paragraphs)
