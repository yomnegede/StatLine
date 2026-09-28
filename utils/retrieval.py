"""Small source selection helper shared by the notebook and API."""

import re


def select_named_sources(question: str, sources: list):
    """Prefer explicitly named players when a question mentions any."""
    question = question.lower()
    selected = []
    for source in sources:
        player = source["player"] if isinstance(source, dict) else source.player
        aliases = {player.lower(), player.split()[-1].lower()}
        if player == "Anthony Edwards":
            aliases.add("ant")
        if any(re.search(rf"\b{re.escape(alias)}\b", question) for alias in aliases):
            selected.append(source)
    return selected or sources
