#!/usr/bin/env python3
"""10Router 对齐与 diff 建议生成器（router_advisor.py）

功能：
1. 只读读取 10Router SQLite 数据库中的 combos（如 yangmao, my-com1）；
2. 关联 free-model-radar 中的 models_current 最新健康状态与测速结果；
3. 计算推荐排位调整：将健康、高吞吐（tps）、低延迟的主力模型前置，降级或剔除异常/死掉的模型；
4. 输出清晰的 diff 结构与排位理由。
"""

import json
import os
import sqlite3
import yaml

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/vendors.yaml")


def load_config(config_path=DEFAULT_CONFIG_PATH):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_10router_combos(router_db_path):
    """只读查询 10Router combos 表"""
    conn = sqlite3.connect(f"file:{router_db_path}?mode=ro", uri=True)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name, models FROM combos").fetchall()
    conn.close()

    combos = {}
    for cid, name, models_json in rows:
        try:
            models_list = json.loads(models_json)
        except Exception:
            models_list = []
        combos[name] = {
            "id": cid,
            "name": name,
            "models": models_list
        }
    return combos


def get_radar_models_status(radar_db_path):
    """读取 model-radar.sqlite models_current 最新快照"""
    if not os.path.exists(radar_db_path):
        return {}
    conn = sqlite3.connect(radar_db_path)
    cur = conn.cursor()
    cur.execute("SELECT model_id, vendor, status, verdict, measured_specs, updated_at FROM models_current")
    rows = cur.fetchall()
    conn.close()

    status_map = {}
    for mid, vendor, status, verdict, specs_str, updated_at in rows:
        specs = {}
        if specs_str:
            try:
                specs = json.loads(specs_str)
            except Exception:
                pass
        status_map[mid] = {
            "model_id": mid,
            "vendor": vendor,
            "status": status,
            "verdict": verdict,
            "latency_ms": specs.get("latency_ms", 9999),
            "tps": specs.get("tps") or 0,
            "updated_at": updated_at
        }
    return status_map


def generate_combo_diff(combo_name="yangmao", config=None):
    """生成指定 combo 的重排或换血 diff 建议"""
    if config is None:
        config = load_config()

    defaults = config.get("defaults", {})
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")
    radar_db = defaults.get("sqlite_db", "/home/linxuan/.hermes/data/model-radar.sqlite")

    combos = get_10router_combos(router_db)
    if combo_name not in combos:
        return {"ok": False, "error": f"Combo '{combo_name}' not found in 10Router"}

    current_models = combos[combo_name]["models"]
    radar_status = get_radar_models_status(radar_db)

    # 评分函数：状态 alive 优先，verdict 为 primary 优先，tps 高优先，latency 低优先
    def score_model(m):
        st = radar_status.get(m)
        if not st:
            return (1, 0, 0, -9999)  # 未知状态，保持中间
        status_score = 3 if st["status"] == "alive" else (1 if st["status"] == "degraded" else 0)
        verdict_score = 2 if st["verdict"] == "primary" else (1 if st["verdict"] == "fallback" else 0)
        tps = st.get("tps") or 0
        latency = -(st.get("latency_ms") or 9999)
        return (status_score, verdict_score, tps, latency)

    # 生成推荐排位
    recommended_models = sorted(current_models, key=score_model, reverse=True)

    changes = []
    for idx, (curr, rec) in enumerate(zip(current_models, recommended_models)):
        if curr != rec:
            changes.append({
                "pos": idx,
                "current": curr,
                "recommended": rec,
                "reason": f"实测状态/吞吐更优: {radar_status.get(rec, {}).get('verdict', 'normal')}"
            })

    # 检查当前是否有死掉的模型排在靠前
    dead_in_front = [
        m for m in current_models[:3]
        if radar_status.get(m, {}).get("status") == "dead"
    ]

    has_diff = (current_models != recommended_models)

    reason = "模型状态与吞吐量重排序优化"
    if dead_in_front:
        reason = f"紧急后移或剔除已失效模型: {', '.join(dead_in_front)}"
    elif not has_diff:
        reason = "当前排位健康稳定，无需调整"

    return {
        "ok": True,
        "combo_name": combo_name,
        "has_diff": has_diff,
        "current_order": current_models,
        "recommended_order": recommended_models,
        "reason": reason,
        "details": changes
    }


def apply_combo_ranking(combo_name="yangmao", new_order=None, config=None, dry_run=False):
    """安全应用排位到 10Router 数据库 combos 表中。
    
    安全机制：
    1. 必须做参数防呆验证（combo 存在，new_order 为非空列表，不丢弃已有模型或包含非法格式）；
    2. 更新前先读取旧配置，在同一目录生成带有时间戳的快照备份 JSON 文件；
    3. 写入后返回执行状态及备份路径。
    """
    if config is None:
        config = load_config()

    defaults = config.get("defaults", {})
    router_db = defaults.get("router_db", "/home/linxuan/.10router-bare-data/db/data.sqlite")

    if not os.path.exists(router_db):
        return {"ok": False, "error": f"10Router 数据库不存在: {router_db}"}

    # 1. 验证 combo 存在并读取原配置
    combos = get_10router_combos(router_db)
    if combo_name not in combos:
        return {"ok": False, "error": f"Combo '{combo_name}' 在 10Router 中不存在"}

    current_models = combos[combo_name]["models"]

    # 如果未指定 new_order，则调用 generate_combo_diff 自动计算推荐排位
    if new_order is None:
        diff = generate_combo_diff(combo_name, config)
        if not diff.get("ok"):
            return diff
        new_order = diff.get("recommended_order", [])

    # 防呆校验
    if not isinstance(new_order, list) or len(new_order) == 0:
        return {"ok": False, "error": "new_order 必须是非空列表"}

    # 校验模型集合是否一致（防止静默漏掉模型）
    if set(current_models) != set(new_order):
        return {
            "ok": False,
            "error": f"模型集合不匹配！原集合: {set(current_models)}, 新集合: {set(new_order)}"
        }

    # 2. 写入前快照备份
    import time
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = os.path.dirname(router_db)
    backup_file = os.path.join(backup_dir, f"combos-bak-{combo_name}-{timestamp}.json")

    backup_data = {
        "combo_name": combo_name,
        "backup_time": timestamp,
        "previous_models": current_models,
        "all_combos_snapshot": combos
    }

    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"ok": False, "error": f"创建备份快照失败: {str(e)}"}

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "combo_name": combo_name,
            "backup_file": backup_file,
            "previous_models": current_models,
            "new_models": new_order,
            "msg": "Dry-run 校验通过，未真正写入数据库"
        }

    # 3. 写入 10Router 数据库
    try:
        conn = sqlite3.connect(router_db)
        cur = conn.cursor()
        now_iso = time.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "UPDATE combos SET models = ?, updatedAt = ? WHERE name = ?",
            (json.dumps(new_order, ensure_ascii=False), now_iso, combo_name)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        return {"ok": False, "error": f"写入 10Router 数据库失败: {str(e)}", "backup_file": backup_file}

    return {
        "ok": True,
        "combo_name": combo_name,
        "backup_file": backup_file,
        "previous_models": current_models,
        "applied_models": new_order,
        "updated_at": now_iso
    }


if __name__ == "__main__":
    diff = generate_combo_diff("yangmao")
    print(json.dumps(diff, ensure_ascii=False, indent=2))

