import re

from autohs.constants import *
from autohs.logs.choices import parse_choice_line
from autohs.logs.events import LineInfoContainer, fetch_entity_id

# "D 04:23:18.0000001 GameState.DebugPrintPower() -     GameEntity EntityID=1"
GAME_STATE_PATTERN = re.compile(r"D [\d]{2}:[\d]{2}:[\d]{2}.[\d]{7} GameState.DebugPrint(Game|Power)\(\) - (.+)")

# "GameEntity EntityID=1"
GAME_ENTITY_PATTERN = re.compile(r" *GameEntity EntityID=(\d+)")

# "Player EntityID=2 PlayerID=1 GameAccountId=[hi=112233445566778899 lo=223344556]"
PLAYER_PATTERN = re.compile(r" *Player EntityID=(\d+) PlayerID=(\d+).*")

# "FULL_ENTITY - Creating ID=89 CardID=EX1_538t"
# "FULL_ENTITY - Creating ID=90 CardID="
# "FULL_ENTITY - Updating [entityName=... id=43 ...] CardID="
FULL_ENTITY_PATTERN = re.compile(r" *FULL_ENTITY - (?:Creating|Updating) (.*?) CardID=(.*)")

# "SHOW_ENTITY - Updating Entity=90 CardID=NEW1_033o"
# "SHOW_ENTITY - Updating Entity=[entityName=UNKNOWN ENTITY [cardType=INVALID] id=32 zone=DECK zonePos=0 cardId= player=1] CardID=VAN_EX1_539"
SHOW_ENTITY_PATTERN = re.compile(r" *SHOW_ENTITY - Updating Entity=(.*) CardID=(.*) *")

# CHANGE_ENTITY 比较罕见，主要对应“呱”等变形行为
# "CHANGE_ENTITY - Updating Entity=[entityName=凯恩·血蹄 id=37 zone=PLAY zonePos=3 cardId=VAN_EX1_110 player=2] CardID=hexfrog"
CHANGE_ENTITY_PATTERN = re.compile(r" *CHANGE_ENTITY - Updating Entity=(.*) CardID=(.*) *")

# "BLOCK_START BlockType=DEATHS Entity=GameEntity EffectCardId=System.Collections.Generic.List`1[System.String] EffectIndex=0 Target=0 SubOption=-1 "
BLOCK_START_PATTERN = re.compile(r" *BLOCK_START BlockType=([A-Z]+) Entity=(.*) EffectCardId=.*")

# "BLOCK_END"
BlOCK_END_PATTERN = re.compile(r" *BLOCK_END *")

# "PlayerID=1, PlayerName=UNKNOWN HUMAN PLAYER"
# "PlayerID=2, PlayerName=Example#51234"
PLAYER_ID_PATTERN = re.compile(r"PlayerID=(\d+), PlayerName=(.*)")

# "TAG_CHANGE Entity=GameEntity tag=NEXT_STEP value=FINAL_WRAPUP "
# "TAG_CHANGE Entity=Example#51234 tag=467 value=4 "
# "TAG_CHANGE Entity=[entityName=UNKNOWN ENTITY [cardType=INVALID] id=14 zone=DECK zonePos=0 cardId= player=1] tag=ZONE value=HAND "
TAG_CHANGE_PATTERN = re.compile(r" *TAG_CHANGE Entity=(.*) tag=(.*) value=(.*) ")

# "tag=ZONE value=DECK"
TAG_PATTERN = re.compile(r" *tag=(.*) value=(.*)")

def parse_line(line_str):
    choice = parse_choice_line(line_str)
    if choice is not None:
        return choice
    match_obj = GAME_STATE_PATTERN.match(line_str)
    if match_obj is None:
        return

    line_str = match_obj.group(2)

    if line_str == "CREATE_GAME":
        return LineInfoContainer(LOG_LINE_CREATE_GAME)

    match_obj = TAG_CHANGE_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_TAG_CHANGE,
            entity=fetch_entity_id(match_obj.group(1)),
            tag=match_obj.group(2),
            value=match_obj.group(3),
        )

    match_obj = TAG_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_TAG,
            tag=match_obj.group(1),
            value=match_obj.group(2)
        )

    match_obj = GAME_ENTITY_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_GAME_ENTITY,
            entity=match_obj.group(1)
        )

    match_obj = PLAYER_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_PLAYER_ENTITY,
            entity=match_obj.group(1),
            player=match_obj.group(2)
        )

    match_obj = FULL_ENTITY_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_FULL_ENTITY,
            entity=fetch_entity_id(match_obj.group(1).removeprefix("ID=")),
            card=match_obj.group(2)
        )

    match_obj = SHOW_ENTITY_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_SHOW_ENTITY,
            entity=fetch_entity_id(match_obj.group(1)),
            card=match_obj.group(2)
        )

    match_obj = CHANGE_ENTITY_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_CHANGE_ENTITY,
            entity=fetch_entity_id(match_obj.group(1)),
            card=match_obj.group(2)
        )

    match_obj = BLOCK_START_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_BLOCK_START,
            type=match_obj.group(1),
            card=match_obj.group(2)
        )

    match_obj = BlOCK_END_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_BLOCK_END
        )

    match_obj = PLAYER_ID_PATTERN.match(line_str)
    if match_obj is not None:
        return LineInfoContainer(
            LOG_LINE_PLAYER_ID,
            player=match_obj.group(1),
            name=match_obj.group(2)
        )

    return None
