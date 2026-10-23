from autohs.behaviors.basic import Coin
from autohs.behaviors.death_knight import (
    Asphyxiate,
    DiscoverMinion,
    DownWithTheShip,
    DrawMinion,
    DrBoom,
    GhoulCharge,
    GraveStrength,
    MiningCasualties,
    RemnantOfRage,
    RiteOfAtrocity,
    SkeletalSidekick,
)
from autohs.behaviors.demon_hunter import (
    Alanna,
    AldrachiWarblades,
    Battlefiend,
    ChaosStrike,
    CoconutCannoneer,
    CrimsonSigilRunner,
    DemonBite,
    DemonClaws,
    DemonHunterAcupuncture,
    EyeBeam,
    Felscreamer,
    GanargBrute,
    GlidingWings,
    IgneousHeart,
    IllidariInquisitor,
    IllidariStudies,
    KaynSunfury,
    MiningAxe,
    MurlocTidehunter,
    OgreNinja,
    PatchesThePilot,
    PirateDealer,
    PirateSupport,
    PowerCountZilliax,
    PrimevalLord,
    RushSpell,
    SpectralSight,
)
from autohs.behaviors.detail import *
from autohs.behaviors.hero import *
from autohs.behaviors.tavern_brawl import (
    Advantage,
    Cliffside,
    EmberRune,
    EmergencyMeeting,
    FirstArgusPortal,
    Headhunt,
    Infestation,
    PerpetualLegacy,
)

ID2CARD_DICT = {
    "TOY_330t5": PowerCountZilliax,
    "VAC_933": PatchesThePilot,
    "VAC_927": PirateSupport,
    "VAC_938": PirateSupport,
    "VAC_532": CoconutCannoneer,
    "VAC_501": Alanna,
    "NEW1_027": PirateSupport,
    "CORE_NEW1_027": PirateSupport,
    "VAN_NEW1_027": PirateSupport,
    "HERO_11bp": GhoulCharge,
    "HERO_11bp2": GhoulCharge,
    "HERO_10bp": DemonClaws,
    "HERO_10bp2": DemonBite,
    "HERO_10cbp": DemonClaws,
    "YOP_001": IllidariStudies,
    "CORE_YOP_001": IllidariStudies,
    "BT_491": SpectralSight,
    "CORE_BT_491": SpectralSight,
    "BT_035": ChaosStrike,
    "CORE_BT_035": ChaosStrike,
    "BT_801": EyeBeam,
    "CORE_BT_801": EyeBeam,
    "BT_921": AldrachiWarblades,
    "CORE_BT_921": AldrachiWarblades,
    "VAC_928": GlidingWings,
    "DEEP_014": MiningAxe,
    "DEEP_011": IgneousHeart,
    "JAM_017": RushSpell,
    "EX1_506": MurlocTidehunter,
    "CORE_EX1_506": MurlocTidehunter,
    "BT_416": Felscreamer,
    "CORE_BT_416": Felscreamer,
    "BT_480": CrimsonSigilRunner,
    "CORE_BT_480": CrimsonSigilRunner,
    "CATA_EVENT_000": PrimevalLord,
    "BT_187": KaynSunfury,
    "CORE_BT_187": KaynSunfury,
    "BT_351": Battlefiend,
    "CORE_BT_351": Battlefiend,
    "GIL_534": GanargBrute,
    "CORE_GIL_534": GanargBrute,
    "CS3_020": IllidariInquisitor,
    "CS2_200": OgreNinja,
    "Core_CS2_200": OgreNinja,
    "EX1_028": OgreNinja,
    "CORE_EX1_028": OgreNinja,
    "VAN_EX1_028": OgreNinja,
    "EDR_811": RiteOfAtrocity,
    "RLK_958": SkeletalSidekick,
    "RLK_116": DiscoverMinion,
    "CORE_RLK_116": DiscoverMinion,
    "LOE_047": DiscoverMinion,
    "TTN_454": DownWithTheShip,
    "DEEP_017": MiningCasualties,
    "RLK_708": DrawMinion,
    "RLK_087": Asphyxiate,
    "CORE_RLK_087": Asphyxiate,
    "RLK_707": GraveStrength,
    "END_004": RemnantOfRage,
    "GVG_110": DrBoom,
    "CORE_GVG_110": DrBoom,
    "GDB_473": Headhunt,  # 猎头
    "END_007": Advantage,  # 发挥优势
    "GDB_119": EmergencyMeeting,  # 紧急会议
    "TLC_902": Infestation,  # 虫害侵扰
    "FIR_902": EmberRune,  # 燃薪咒符
    "TIME_020t2": FirstArgusPortal,  # 第一道阿古斯传送门
    "VAC_929": Cliffside,  # 惊险悬崖
    "TIME_449": PerpetualLegacy,  # 绵延传承
    # 特殊项-幸运币
    "COIN": Coin,

    # 英雄技能
    # 注意：英雄技能通过 detail_hero_power() 驱动
    "TOTEMIC_CALL": TotemicCall,
    "LESSER_HEAL": LesserHeal,
    "BALLISTA_SHOT": BallistaShot,
    "MIND_SPIKE": MindSpike,

    # 部分牧师卡
    "YOP_032": ArmorVendor,  # 护甲商贩
    "CORE_CS1_130": HolySmite,  # 神圣惩击
    "CS1_130": HolySmite,  # 神圣惩击
    "SCH_250": WaveOfApathy,  # 倦怠光波
    "BT_715": BonechewerBrawler,  # 噬骨殴斗者
    "CORE_EX1_622": ShadowWordDeath,  # 暗言术：灭
    "EX1_622": ShadowWordDeath,  # 暗言术：灭
    "BT_257": Apotheosis,  # 神圣化身
    "BAR_026": DeathsHeadCultist,  # 亡首教徒
    "BAR_311": DevouringPlague,  # 噬灵疫病
    "BT_730": OverconfidentOrc,  # 狂傲的兽人
    "CORE_CS1_112": HolyNova,  # 神圣新星
    "CS1_112": HolyNova,  # 神圣新星
    "YOP_006": Hysteria,  # 狂乱
    "CORE_EX1_197": ShadowWordRuin,  # 暗言术：毁
    "EX1_197": ShadowWordRuin,  # 暗言术：毁
    "WC_014": AgainstAllOdds,  # 除奇致胜
    "BT_720": RuststeedRaider,  # 锈骑劫匪
    "CS3_024": TaelanFordring,  # 泰兰·弗丁
    "EX1_110": CairneBloodhoof,  # 凯恩·血蹄
    "CORE_EX1_110": CairneBloodhoof,  # 凯恩·血蹄
    "WC_030": MutanusTheDevourer,  # 吞噬者穆坦努斯
    "BT_198": SoulMirror,  # 灵魂之镜
    "DMF_053": BloodOfGhuun,  # 戈霍恩之血

    # 经典模式
    "VAN_CS2_042": FireElemental,
    "VAN_EX1_562": Onyxia,
    "VAN_EX1_248": FeralSpirit,
    "VAN_EX1_246": Hex,
    "VAN_EX1_238": LightingBolt,
    "VAN_EX1_085": MindControlTech,
    "VAN_EX1_284": AzureDrake,
    "VAN_EX1_259": LightningStorm,
    "VAN_CS2_189": ElvenArcher,
    "VAN_CS2_117": EarthenRingFarseer,
    "VAN_EX1_097": Abomination,
    "VAN_NEW1_021": DoomSayer,
    "VAN_NEW1_041": StampedingKodo,
    "VAN_EX1_590": BloodKnight,
    "VAN_EX1_247": StormforgedAxe,

    # 暗牧
    "CFM_637": PatchesThePirate,
    "SW_446": VoidtouchedAttendant,
    "TOY_518": PirateDealer,
    "VAC_512": MindrenderIllucia,
    "NAX4_04": RaiseDead,
    "NAX4_04H": RaiseDead,
    "SCH_514": RaiseDead,
    "GVG_009": ShadowBomber,
    "WON_062": ShadowBomber,
    "NX2_019": MindBlast,
    "VAC_419": DemonHunterAcupuncture,
    "CORE_WON_065": ShipSurgeon,
    "WON_065": ShipSurgeon,
    "DS1_233": MindShatter,
    "VAN_DS1_233": MindShatter,
    "SW_444": TwilightDeceptor,
    "DRG_056": CathedralOfAtonement,
    "TOY_381": PaperCranes,
    # "CORE_REV_290": CathedralOfAtonement,
    # "REV_290": CathedralOfAtonement,
    # "REV_791": CathedralOfAtonement,
    "CORE_SW_448": DarkbishopBenedictus,
    "SW_448": DarkbishopBenedictus,
    "DED_513": DefiasCleaner,
    "YOD_032": FrenziedFelwing,
    "REV_791": ChurchOfAtonement,
    "CORE_REV_290": ChurchOfAtonement,
    "REV_290": ChurchOfAtonement,
}
