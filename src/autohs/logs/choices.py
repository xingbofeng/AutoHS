"""Discover packets and visibility signals from Power.log."""

import re

from autohs.logs.events import LineInfoContainer, fetch_entity_id


def parse_choice_line(line):
    match = re.match(
        r"D \S+ GameState\.DebugPrintEntityChoices\(\) -\s*(.*)", line,
    )
    if match:
        body = match.group(1)
        header = re.match(
            r"id=(\d+) Player=(.*?) TaskList=\d+ ChoiceType=(\w+) CountMin=(\d+) CountMax=(\d+)",
            body,
        )
        if header:
            choice_id, player, kind, minimum, maximum = header.groups()
            return LineInfoContainer(
                "Choice Start", choice_id=choice_id, player=player, kind=kind,
                minimum=int(minimum), maximum=int(maximum),
            )
        if body.startswith("Source="):
            source = body[len("Source="):]
            owner = re.search(r"\bplayer=(\d+)", source)
            return LineInfoContainer(
                "Choice Source", source=fetch_entity_id(source),
                owner=owner.group(1) if owner else None,
            )
        option = re.match(r"Entities\[(\d+)\]=(.*)", body)
        if option:
            return LineInfoContainer(
                "Choice Option", index=int(option.group(1)),
                entity=fetch_entity_id(option.group(2)),
            )
    ready = re.search(r"ChoiceCardMgr\.WaitThenShowChoices\(\) - id=(\d+) BEGIN", line)
    if ready:
        return LineInfoContainer("Choice Ready", choice_id=ready.group(1))
    chosen = re.search(r"GameState\.DebugPrintEntitiesChosen\(\) - id=(\d+) ", line)
    if chosen:
        return LineInfoContainer("Choice Done", choice_id=chosen.group(1))
    sent = re.search(r"GameState\.SendChoices\(\) - id=(\d+) ChoiceType=", line)
    if sent:
        return LineInfoContainer("Choice Done", choice_id=sent.group(1))
    return None
