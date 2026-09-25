"""
# 通配规则
# standards_format: <type:arg_name>
# 1. <type:(arg_name)>
# 2. <(str:)arg_name> or <:agr_name>
# 3. * 也表示 <str:>
"""
from re import escape, Pattern, compile

TYPE_MAP = {
    "uuid": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "str": ".+",
    "int": r"\d+"
}

def is_match_cmd(cmd: str) -> bool:
    return "<" in cmd or "*" in cmd

def to_pat(cmd: str) -> Pattern:
    # 由AI编写, 未来可能出现问题
    if cmd == "*":
        return compile("^.*$")

    parts = []
    i = 0

    while i < len(cmd):

        if cmd[i] == "<":
            end = cmd.index(">", i)
            inner = cmd[i+1:end]
            if ":" in inner:
                type_, name_ = inner.split(":", 1)
            else:
                type_, name_ = "str", inner
            regex = TYPE_MAP.get(type_, TYPE_MAP["str"])
            parts.append(f"(?P<{name_}>{regex})")
            i = end + 1
        else:
            parts.append(escape(cmd[i]))
            i += 1

    return compile(f"^{''.join(parts)}$")