from __future__ import annotations

TEAM_TRANSLATIONS = {
    "Algeria": "阿尔及利亚",
    "Argentina": "阿根廷",
    "Australia": "澳大利亚",
    "Austria": "奥地利",
    "Belgium": "比利时",
    "Bosnia and Herzegovina": "波黑",
    "Brazil": "巴西",
    "Canada": "加拿大",
    "Cape Verde": "佛得角",
    "Colombia": "哥伦比亚",
    "Croatia": "克罗地亚",
    "Curaçao": "库拉索",
    "Czech Republic": "捷克",
    "DR Congo": "刚果民主共和国",
    "Ecuador": "厄瓜多尔",
    "Egypt": "埃及",
    "England": "英格兰",
    "France": "法国",
    "Germany": "德国",
    "Ghana": "加纳",
    "Haiti": "海地",
    "Iran": "伊朗",
    "Iraq": "伊拉克",
    "Ivory Coast": "科特迪瓦",
    "Japan": "日本",
    "Jordan": "约旦",
    "Mexico": "墨西哥",
    "Morocco": "摩洛哥",
    "Netherlands": "荷兰",
    "New Zealand": "新西兰",
    "Norway": "挪威",
    "Panama": "巴拿马",
    "Paraguay": "巴拉圭",
    "Portugal": "葡萄牙",
    "Qatar": "卡塔尔",
    "Saudi Arabia": "沙特阿拉伯",
    "Scotland": "苏格兰",
    "Senegal": "塞内加尔",
    "South Africa": "南非",
    "South Korea": "韩国",
    "Spain": "西班牙",
    "Sweden": "瑞典",
    "Switzerland": "瑞士",
    "Tunisia": "突尼斯",
    "Turkey": "土耳其",
    "United States": "美国",
    "Uruguay": "乌拉圭",
    "Uzbekistan": "乌兹别克斯坦",
}

TEAM_RANKINGS = {
    "Argentina": 1,
    "Spain": 2,
    "France": 3,
    "England": 4,
    "Portugal": 5,
    "Brazil": 6,
    "Morocco": 7,
    "Netherlands": 8,
    "Belgium": 9,
    "Germany": 10,
    "Croatia": 11,
    "Colombia": 13,
    "Mexico": 14,
    "Senegal": 15,
    "Uruguay": 16,
    "United States": 17,
    "Japan": 18,
    "Switzerland": 19,
    "Iran": 20,
    "Turkey": 22,
    "Ecuador": 23,
    "Austria": 24,
    "South Korea": 25,
    "Australia": 27,
    "Algeria": 28,
    "Egypt": 29,
    "Canada": 30,
    "Norway": 31,
    "Ivory Coast": 33,
    "Panama": 34,
    "Sweden": 38,
    "Czech Republic": 40,
    "Paraguay": 41,
    "Scotland": 42,
    "Tunisia": 45,
    "DR Congo": 46,
    "Uzbekistan": 50,
    "Qatar": 56,
    "Iraq": 57,
    "South Africa": 60,
    "Saudi Arabia": 61,
    "Jordan": 63,
    "Bosnia and Herzegovina": 64,
    "Cape Verde": 67,
    "Ghana": 73,
    "Curaçao": 82,
    "Haiti": 83,
    "New Zealand": 85,
}

PLAYER_TRANSLATIONS = {
    "Crysencio Summerville": "克里森西奥·萨默维尔",
    "Connor Metcalfe": "康纳·梅特卡夫",
    "Cyle Larin": "凯尔·拉林",
    "Daichi Kamada": "镰田大地",
    "Damián Bobadilla": "达米安·博瓦迪利亚",
    "Deniz Undav": "德尼兹·翁达夫",
    "Felix Nmecha": "费利克斯·恩梅查",
    "Folarin Balogun": "福拉林·巴洛贡",
    "Giovanni Reyna": "乔瓦尼·雷纳",
    "Hwang In-beom": "黄仁范",
    "Ismael Saibari": "伊斯梅尔·赛巴里",
    "Jamal Musiala": "贾马尔·穆西亚拉",
    "John McGinn": "约翰·麦金",
    "Jovo Lukić": "约沃·卢基奇",
    "Julián Quiñones": "胡利安·基尼奥内斯",
    "Keito Nakamura": "中村敬斗",
    "Ladislav Krejčí": "拉迪斯拉夫·克雷伊奇",
    "Livano Comenencia": "利瓦诺·科梅嫩西亚",
    "Maurício": "毛里西奥",
    "Miro Muheim": "米罗·穆海姆",
    "Nathaniel Brown": "纳撒尼尔·布朗",
    "Nestory Irankunda": "内斯托里·伊兰昆达",
    "Nico Schlotterbeck": "尼科·施洛特贝克",
    "Oh Hyeon-gyu": "吴贤揆",
    "Raúl Jiménez": "劳尔·希门尼斯",
    "Virgil van Dijk": "维吉尔·范戴克",
}

GROUP_TRANSLATIONS = {
    "A": "A组",
    "B": "B组",
    "C": "C组",
    "D": "D组",
    "E": "E组",
    "F": "F组",
    "G": "G组",
    "H": "H组",
    "I": "I组",
    "J": "J组",
    "K": "K组",
    "L": "L组",
}


def display_team_name(name: str, include_ranking: bool = True) -> str:
    chinese = _translate_placeholder(name) or TEAM_TRANSLATIONS.get(name)
    if not chinese:
        return name
    ranking = TEAM_RANKINGS.get(name)
    if ranking is None or not include_ranking:
        return f"{chinese}（{name}）"
    return f"{chinese}（{name}，世界排名第{ranking}）"


def display_player_name(name: str, chinese: str = "") -> str:
    translated = chinese or PLAYER_TRANSLATIONS.get(name, "")
    if not translated:
        return name
    return f"{translated}（{name}）"


def _translate_placeholder(name: str) -> str | None:
    if name == "Winner":
        return "胜者"
    if name == "Loser":
        return "负者"

    if name.startswith("Winner Group "):
        group = name.removeprefix("Winner Group ")
        return f"{_group_name(group)}第一名"
    if name.startswith("Runner-up Group "):
        group = name.removeprefix("Runner-up Group ")
        return f"{_group_name(group)}第二名"
    if name.startswith("3rd Group "):
        groups = name.removeprefix("3rd Group ")
        return f"{'/'.join(_group_name(group) for group in groups.split('/'))}第三名"
    return None


def _group_name(group: str) -> str:
    return GROUP_TRANSLATIONS.get(group, f"{group}组")
