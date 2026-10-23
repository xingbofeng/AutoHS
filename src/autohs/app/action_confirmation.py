"""Confirm an input against the original Power.log entity, not a UI index."""

from dataclasses import dataclass

_COMBAT_TAGS = (
    "ATK",
    "HEALTH",
    "DAMAGE",
    "ARMOR",
    "DURABILITY",
    "TAUNT",
    "DIVINE_SHIELD",
    "STEALTH",
    "IMMUNE",
    "UNTOUCHABLE",
    "DORMANT",
    "POISONOUS",
    "LIFESTEAL",
    "WINDFURY",
    "CHARGE",
    "RUSH",
    "ATTACKABLE_BY_RUSH",
    "FROZEN",
    "FREEZE",
    "CANT_ATTACK",
    "EXHAUSTED",
    "NUM_ATTACKS_THIS_TURN",
    "NUM_TURNS_IN_PLAY",
    "CANT_BE_TARGETED_BY_SPELLS",
    "CANT_BE_TARGETED_BY_HERO_POWERS",
    "SILENCED",
    "SPELLPOWER",
    "BATTLECRY",
    "COST",
    "TAG_LAST_KNOWN_COST_IN_HAND",
    "OVERLOAD",
    "POWERED_UP",
    "COOLDOWN",
    "LOCATION_COOLDOWN",
    "LOCATION_ACTION_COOLDOWN",
    "RESOURCES",
    "RESOURCES_USED",
    "TEMP_RESOURCES",
)


def _number(tags, tag):
    return int(tags.get(tag, "0"))


def _layout(log):
    return {
        entity_id: (
            entity.query_tag("ZONE"),
            entity.query_tag("ZONE_POSITION"),
            entity.query_tag("CONTROLLER"),
            entity.query_tag("CARDTYPE"),
            getattr(entity, "card_id", None),
        )
        for entity_id, entity in log.entity_dict.items()
        if entity.query_tag("ZONE") in ("HAND", "PLAY")
    }


def _combat_state(log):
    # Include potential targets and auras, but ignore hidden cards and metadata.
    return {
        entity_id: tuple(entity.query_tag(tag) for tag in _COMBAT_TAGS)
        for entity_id, entity in log.entity_dict.items()
        if entity.query_tag("ZONE") == "PLAY"
        or entity_id == getattr(log, "my_entity_id", None)
        or (
            entity.query_tag("ZONE") == "HAND"
            and entity.query_tag("CONTROLLER") == log.my_player_id
        )
    }


def _actor(log, action, index):
    entities = [
        (entity_id, entity)
        for entity_id, entity in log.entity_dict.items()
        if entity.query_tag("CONTROLLER") == log.my_player_id
    ]
    if index == -1 and action in ("attack", "card"):
        cardtype = "HERO" if action == "attack" else "HERO_POWER"
        candidates = [
            item
            for item in entities
            if item[1].query_tag("ZONE") == "PLAY"
            and item[1].query_tag("CARDTYPE") == cardtype
        ]
        return candidates[-1] if candidates else None
    if index < 0:
        return None
    candidates = [
        item
        for item in entities
        if (
            item[1].query_tag("ZONE") == "HAND"
            if action == "card"
            else item[1].query_tag("ZONE") == "PLAY"
            and item[1].query_tag("CARDTYPE") in ("MINION", "LOCATION")
        )
    ]
    candidates.sort(key=lambda item: int(item[1].query_tag("ZONE_POSITION")))
    return candidates[index] if index < len(candidates) else None


@dataclass(frozen=True)
class ActionConfirmation:
    action: str
    index: int
    entity_id: str
    before: dict
    context: tuple
    layout: dict
    combat_state: dict

    @staticmethod
    def _context(log):
        return (
            id(log),
            getattr(log, "game_entity_id", None),
            log.game_num_turns_in_play,
        )

    @classmethod
    def capture(cls, log, strategy, action, index):
        actor = _actor(log, action, index)
        if actor is None:
            return None
        entity_id, entity = actor
        if action == "location" and entity.query_tag("CARDTYPE") != "LOCATION":
            return None
        if action == "attack" and entity.query_tag("CARDTYPE") == "LOCATION":
            return None

        # Strategy entities currently omit IDs. Validate optional metadata and
        # reproduce StrategyState's ordering to bind the input to a log ID.
        if index == -1:
            name = "my_hero" if action == "attack" else "my_hero_power"
            selected = getattr(strategy, name, None)
        else:
            name = "my_hand_cards" if action == "card" else "my_minions"
            collection = getattr(strategy, name, None)
            if collection is not None and index >= len(collection):
                return None
            selected = collection[index] if collection is not None else None
        if selected is not None:
            if getattr(
                selected, "card_id", None
            ) is not None and selected.card_id != getattr(entity, "card_id", None):
                return None
            if getattr(
                selected, "zone_pos", None
            ) is not None and selected.zone_pos != int(
                entity.query_tag("ZONE_POSITION")
            ):
                return None
        return cls(
            action,
            index,
            entity_id,
            dict(entity.tag_dict),
            cls._context(log),
            _layout(log),
            _combat_state(log),
        )

    def same_context(self, log):
        return not log.is_end and log.is_my_turn and self.context == self._context(log)

    def current(self, log):
        actor = _actor(log, self.action, self.index)
        return (
            self.same_context(log)
            and getattr(log, "pending_choice", None) is None
            and actor is not None
            and actor[0] == self.entity_id
            and self.layout == _layout(log)
            and self.combat_state == _combat_state(log)
        )

    def confirmed(self, log):
        if not self.same_context(log):
            return False
        entity = log.entity_dict.get(self.entity_id)
        if entity is None:
            return False
        after = entity.tag_dict
        if self.action == "card" and self.index >= 0:
            return self.before.get("ZONE") == "HAND" and after.get("ZONE") not in (
                None,
                "0",
                "HAND",
            )
        if after.get("CONTROLLER") != self.before.get("CONTROLLER"):
            return False
        exhausted = (
            after.get("EXHAUSTED") == "1" and self.before.get("EXHAUSTED", "0") == "0"
        )
        if self.action == "attack":
            left_play = self.before.get("ZONE") == "PLAY" and after.get("ZONE") not in (
                None,
                "0",
                "PLAY",
            )
            return (
                exhausted
                or left_play
                or (
                    _number(after, "NUM_ATTACKS_THIS_TURN")
                    > _number(self.before, "NUM_ATTACKS_THIS_TURN")
                )
            )
        if self.action == "location":
            return (
                exhausted
                or any(
                    _number(after, tag) > _number(self.before, tag)
                    for tag in (
                        "COOLDOWN",
                        "LOCATION_COOLDOWN",
                        "LOCATION_ACTION_COOLDOWN",
                        "DAMAGE",
                    )
                )
                or any(
                    tag in self.before
                    and tag in after
                    and _number(after, tag) < _number(self.before, tag)
                    for tag in ("HEALTH", "DURABILITY")
                )
            )
        return exhausted
