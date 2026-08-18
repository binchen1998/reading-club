"""coding61 章节书 CDN 路径。"""

from __future__ import annotations

CDN = "https://static1.cxy61.com"

SERIES = [
    {
        "id": "FlyGuy",
        "level_name": "bridge-books苍蝇小子",
        "title": "Fly Guy 苍蝇小子",
        "readable": True,
    },
    {
        "id": "FrogAndToad",
        "level_name": "files",
        "title": "Frog and Toad 青蛙与蟾蜍",
        "readable": True,
    },
    {
        "id": "FancyNancy",
        "level_name": "Nancy",
        "title": "Fancy Nancy 漂亮的南希",
        "readable": True,
    },
    {
        "id": "WinnieAndWilbur",
        "level_name": "WinnieAndWilbur",
        "title": "Winnie And Wilbur 女巫温妮",
        "readable": True,
    },
    {
        "id": "MagicTreeHouse",
        "level_name": "MagicTreeHouse",
        "title": "Magic Tree House 神奇树屋",
        "readable": True,
    },
    {
        "id": "CuriousGeorge",
        "level_name": "CuriousGeorge",
        "title": "Curious George 好奇的乔治",
        "readable": True,
    },
    {
        "id": "NateTheGreat",
        "level_name": "NateTheGreat",
        "title": "Nate the Great 大侦探奈特",
        "readable": True,
    },
    {
        "id": "AToZ",
        "level_name": "AToZ",
        "title": "A to Z Mysteries 神秘案件",
        "readable": True,
    },
    {
        "id": "CatAndMouse",
        "level_name": "CatAndMouse",
        "title": "老鼠记者",
        "readable": True,
    },
    {
        "id": "DragonMasters",
        "level_name": "DraonMasters",
        "title": "Dragon Masters 驯龙大师",
        "readable": True,
    },
]


def catalog_url(level_name: str) -> str:
    if level_name.startswith("bridge-books") and "苍蝇" in level_name:
        return f"{CDN}/{level_name}/{level_name}.json"
    if level_name == "files":
        return f"{CDN}/bridge-books/files/files.json"
    return f"{CDN}/bridge-books/{level_name}/files/{level_name}.json"


def pages_base(level_name: str, book_name: str) -> str:
    if level_name.startswith("bridge-books") and "苍蝇" in level_name:
        return f"{CDN}/{level_name}/{book_name}/pages"
    if level_name == "files":
        return f"{CDN}/bridge-books/files/{book_name}/pages"
    return f"{CDN}/bridge-books/{level_name}/files/{book_name}/pages"
