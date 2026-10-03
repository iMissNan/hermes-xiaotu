#!/usr/bin/env python3
"""CLI 短指令 / 自然语言路由解析器（cli_handler.py）

前缀指令体系："fm"（Free Model 首字母缩写）
支持命令族：
- fm查 / fm查询 / fm list / fm status:
    查询供应商数据、全览或指定模型/供应商详情
    例: fm查, fm查 cline, fm查 qoder, fm list, fm status
- fm加 / fm添加 / fm add:
    添加供应商或模型进 vendors.yaml
    例: fm加 --vendor siliconflow --doc-url https://siliconflow.cn --models glm-4-flash,deepseek-v3
- fm测 / fm test / fm benchmark:
    即时触发 L1 心跳或 L2 规约深测
    例: fm测 (全量L1), fm测 cline (cline供应商心跳), fm测 cline/z-ai/glm-5.3-flash (L2深测)
- fm换 / fm采纳 / fm apply:
    应用推荐排位，将新排位写入 10Router 数据库（含备份与防呆）
    例: fm换, fm换 yangmao, fm采纳 yangmao, fm apply yangmao
- fm停 / fm删 / fm remove / fm disable:
    停用或移除供应商或模型
    例: fm停 cline, fm删 nvidia
"""

import argparse
import json
import os
import re
import shlex
import sys
import yaml

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from crawler import load_config
from router_advisor import generate_combo_diff, apply_combo_ranking
from run import (
    do_query,
    do_investigate,
    do_add_vendor,
    do_remove_vendor,
    do_heartbeat,
    do_benchmark,
    do_active,
    do_top,
    do_help,
    do_apply
)


def parse_fm_command(cmd_text: str):
    """解析以 fm 开头的自然语言或短指令字符串，返回对应的规范动作及参数"""
    text = cmd_text.strip()
    if not text:
        return {"ok": False, "error": "指令不能为空"}

    # 规范化：去除开头的 / 或 ! 等常见聊天前缀（如 /fm查 -> fm查）
    if text.startswith(("/", "!", "！")):
        text = text[1:].strip()

    # 验证是否以 fm 开头（不区分大小写）
    match = re.match(r"^fm\s*(.*)$", text, re.I)
    if not match:
        return {
            "ok": False,
            "error": f"非 fm 前缀指令。有效前缀须以 'fm' 开头（如 'fm查', 'fm测', 'fm换', 'fm加', 'fm停'）: {cmd_text}"
        }

    rest = match.group(1).strip()
    if not rest:
        # 默认裸 fm 等同于 fm查（全览）
        return {
            "ok": True,
            "action": "query",
            "args": {}
        }

    # 识别动词
    # 帮助/菜单/指令系列 (help)
    if re.match(r"^(指令|帮助|help|menu|菜单)\b", rest, re.I) or rest.startswith(("指令", "帮助", "help", "menu", "菜单")):
        return {
            "ok": True,
            "action": "help",
            "args": {}
        }

    # 全部/有效供应商系列 (active)
    if re.match(r"^(全部供应商|全部|当前入库|现存|活跃|active|all)\b", rest, re.I) or rest.startswith(("全部供应商", "全部", "当前入库", "现存", "活跃", "active", "all")):
        return {
            "ok": True,
            "action": "active",
            "args": {}
        }

    # 榜单/TOP系列 (top)
    if re.match(r"^(榜单|top|rank|排行榜|排行|推荐|榜)\b", rest, re.I) or rest.startswith(("榜单", "top", "rank", "排行榜", "排行", "推荐", "榜")):
        sub = re.sub(r"^(榜单|top|rank|排行榜|排行|推荐|榜)\s*", "", rest, flags=re.I).strip()
        tokens = shlex.split(sub) if sub else []
        limit = 5
        if tokens and tokens[0].isdigit():
            limit = int(tokens[0])
        return {
            "ok": True,
            "action": "top",
            "args": {"limit": limit}
        }

    # 查系列
    if re.match(r"^(查询|查|list|status|ls)\b", rest, re.I) or rest.startswith(("查询", "查", "list", "status", "ls")):
        sub = re.sub(r"^(查询|查|list|status|ls)\s*", "", rest, flags=re.I).strip()
    elif any(k in rest.lower() for k in ["qoder", "workbuddy", "codebuddy", "cline", "amd", "nvidia", "siliconflow"]):
        # 容错：如果用户直接输入 "fm workbuddy" 或 "fm qoder国服"，自动归入查/探查动作
        sub = rest.strip()
    else:
        sub = None

    if sub is not None:
        # 处理自然语言别名匹配
        # 比如：qoder国服 -> qoder-cn, qoder国际服/国际 -> qoder
        # workbuddy国服 -> workbuddy-cn, workbuddy国际服/国际 -> workbuddy
        target_vendors = []
        if any(k in sub for k in ["qoder国服", "qoder-cn"]):
            target_vendors.append("qoder-cn")
        if any(k in sub for k in ["qoder国际服", "qoder国际", "qoder-intl"]) or ("qoder" in sub and "国际" in sub):
            target_vendors.append("qoder")
        elif "qoder" in sub and not any(k in sub for k in ["qoder国服", "qoder-cn"]):
            target_vendors.append("qoder")

        if any(k in sub for k in ["workbuddy国服", "workbuddy-cn"]):
            target_vendors.append("workbuddy-cn")
        if any(k in sub for k in ["workbuddy国际服", "workbuddy国际", "workbuddy-intl"]) or ("workbuddy" in sub and "国际" in sub):
            target_vendors.append("workbuddy")
        elif "workbuddy" in sub and not any(k in sub for k in ["workbuddy国服", "workbuddy-cn"]):
            target_vendors.append("workbuddy")

        if "cline" in sub:
            target_vendors.append("cline")
        if "amd" in sub:
            target_vendors.append("amd")
        if "nvidia" in sub:
            target_vendors.append("nvidia")

        tokens = shlex.split(sub) if sub else []
        vendor = None
        model = None
        # 如果匹配到多目标供应商别名列表
        if target_vendors:
            vendor = ",".join(list(dict.fromkeys(target_vendors)))
        else:
            for t in tokens:
                if "/" in t:
                    model = t
                elif not vendor:
                    vendor = t
                else:
                    model = t
        return {
            "ok": True,
            "action": "investigate",
            "args": {"vendor": vendor, "model": model}
        }

    # 加系列
    if re.match(r"^(添加|加|add)\b", rest, re.I) or rest.startswith(("添加", "加", "add")):
        sub = re.sub(r"^(添加|加|add)\s*", "", rest, flags=re.I).strip()
        # 支持 --vendor V --doc-url URL --models M1,M2 或简写位置参数
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--vendor", "-v")
        parser.add_argument("--doc-url", "-u", default="")
        parser.add_argument("--models", "-m", default="")
        parser.add_argument("pos_args", nargs="*")
        
        try:
            tokens = shlex.split(sub) if sub else []
            parsed, unknown = parser.parse_known_args(tokens)
            vendor = parsed.vendor
            doc_url = parsed.doc_url
            models_str = parsed.models
            if not vendor and parsed.pos_args:
                vendor = parsed.pos_args[0]
            if not models_str and len(parsed.pos_args) > 1:
                models_str = parsed.pos_args[1]
            if not doc_url and len(parsed.pos_args) > 2:
                doc_url = parsed.pos_args[2]

            models_list = [m.strip() for m in models_str.split(",") if m.strip()] if models_str else []
            return {
                "ok": True,
                "action": "add-vendor",
                "args": {
                    "vendor": vendor,
                    "doc_url": doc_url,
                    "models": models_list
                }
            }
        except Exception as e:
            return {"ok": False, "error": f"解析 fm加 参数失败: {str(e)}"}

    # 测系列
    if re.match(r"^(测试|测|test|benchmark|check)\b", rest, re.I) or rest.startswith(("测试", "测", "test", "benchmark", "check")):
        sub = re.sub(r"^(测试|测|test|benchmark|check)\s*", "", rest, flags=re.I).strip()
        tokens = shlex.split(sub) if sub else []
        target = tokens[0] if tokens else None
        
        # 判断是测特定模型（L2）还是测供应商/全量心跳（L1）
        # 若包含斜杠 /，说明是具体模型 ID，走 benchmark (L2)
        if target and ("/" in target or target.count("-") >= 2):
            return {
                "ok": True,
                "action": "benchmark",
                "args": {"model": target}
            }
        else:
            # 否则当做 vendor 或全量心跳
            return {
                "ok": True,
                "action": "heartbeat",
                "args": {"vendor": target if target else None}
            }

    # 换/采纳系列
    if re.match(r"^(采纳|应用|换|apply|swap)\b", rest, re.I) or rest.startswith(("采纳", "应用", "换", "apply", "swap")):
        sub = re.sub(r"^(采纳|应用|换|apply|swap)\s*", "", rest, flags=re.I).strip()
        tokens = shlex.split(sub) if sub else []
        combo = tokens[0] if tokens else "yangmao"
        dry_run = "--dry-run" in tokens
        return {
            "ok": True,
            "action": "apply",
            "args": {"combo": combo, "dry_run": dry_run}
        }

    # 停/删系列
    if re.match(r"^(移除|删除|停用|停|删|remove|disable|del|rm)\b", rest, re.I) or rest.startswith(("移除", "删除", "停用", "停", "删", "remove", "disable", "del", "rm")):
        sub = re.sub(r"^(移除|删除|停用|停|删|remove|disable|del|rm)\s*", "", rest, flags=re.I).strip()
        tokens = shlex.split(sub) if sub else []
        if not tokens:
            return {"ok": False, "error": "fm停/fm删 需要指定供应商名称，如 'fm停 cline'"}
        vendor = tokens[0]
        return {
            "ok": True,
            "action": "remove-vendor",
            "args": {"vendor": vendor}
        }

    # 未识别的 fm 子指令
    return {
        "ok": False,
        "error": f"无法识别的 fm 子指令: '{rest}'。可选：fm 指令, fm 全部, fm 榜单, fm查, fm加, fm测, fm换, fm停"
    }


def execute_fm_command(cmd_text: str):
    """解析并直接执行 fm 指令"""
    parsed = parse_fm_command(cmd_text)
    if not parsed.get("ok"):
        print(f"❌ 指令解析失败: {parsed.get('error')}")
        return False

    action = parsed["action"]
    args = parsed["args"]
    config = load_config()

    if action == "help":
        return do_help(config)
    elif action == "investigate":
        return do_investigate(config, vendor=args.get("vendor"), model=args.get("model"))
    elif action == "query":
        return do_query(config, vendor=args.get("vendor"), model=args.get("model"))
    elif action == "active":
        return do_active(config)
    elif action == "top":
        return do_top(config, limit=args.get("limit", 5))
    elif action == "add-vendor":
        return do_add_vendor(config, vendor=args.get("vendor"), doc_url=args.get("doc_url"), models=args.get("models"))
    elif action == "remove-vendor":
        return do_remove_vendor(config, vendor=args.get("vendor"))
    elif action == "heartbeat":
        return do_heartbeat(config, vendor=args.get("vendor"))
    elif action == "benchmark":
        return do_benchmark(config, model=args.get("model"))
    elif action == "apply":
        return do_apply(config, combo=args.get("combo", "yangmao"), dry_run=args.get("dry_run", False))
    else:
        print(f"❌ 未知操作: {action}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 cli_handler.py \"fm指令\"")
        print("示例: python3 cli_handler.py \"fm查\"")
        print("      python3 cli_handler.py \"fm查 qoder\"")
        print("      python3 cli_handler.py \"fm测 cline\"")
        print("      python3 cli_handler.py \"fm换 yangmao\"")
        sys.exit(1)

    cmd_str = " ".join(sys.argv[1:])
    success = execute_fm_command(cmd_str)
    sys.exit(0 if success else 1)
