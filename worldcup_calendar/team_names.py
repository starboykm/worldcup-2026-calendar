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


def display_team_name(name: str) -> str:
    chinese = _translate_placeholder(name) or TEAM_TRANSLATIONS.get(name)
    if not chinese:
        return name
    return f"{chinese}（{name}）"


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
