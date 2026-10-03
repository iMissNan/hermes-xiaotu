#!/usr/bin/env python3
"""飞书审批卡片格式化生成器（feishu_notifier.py）

功能：
1. 接收 router_advisor.py 产生的 diff 结果；
2. 格式化输出为符合规格说明书要求的飞书审批交互卡片 Markdown 文本；
3. 提供复制即用的回复指引与变更命令。
"""

import json


def format_feishu_approval_card(diff_result):
    """格式化为飞书审批卡片文本"""
    if not diff_result.get("ok"):
        return f"⚠️ 【10Router 免费模型雷达警报】生成建议失败：{diff_result.get('error')}"

    combo_name = diff_result.get("combo_name", "unknown")
    current_order = diff_result.get("current_order", [])
    recommended_order = diff_result.get("recommended_order", [])
    reason = diff_result.get("reason", "常规巡检排位更新")
    has_diff = diff_result.get("has_diff", False)

    curr_str = json.dumps(current_order, ensure_ascii=False)
    rec_str = json.dumps(recommended_order, ensure_ascii=False)

    lines = []
    lines.append("【10Router 免费模型轮替审批卡片】")
    if has_diff:
        lines.append(f"监测到供应商模型池有更优排位，建议调整 combo: [{combo_name}]")
    else:
        lines.append(f"combo [{combo_name}] 巡检完成，当前排位健康稳定。")
    lines.append("--------------------------------------------------")
    lines.append(f"当前排位: {curr_str}")
    lines.append(f"推荐排位: {rec_str}")
    lines.append(f"变动原因: {reason}")
    lines.append("--------------------------------------------------")
    if has_diff:
        lines.append("👉 老板若同意调整，请直接回复【同意变更】或【采纳】，小兔立即代为下发网关！")
    else:
        lines.append("✅ 当前无需变更，继续保持常态化巡检。")

    return "\n".join(lines)


if __name__ == "__main__":
    test_diff = {
        "ok": True,
        "combo_name": "yangmao",
        "has_diff": True,
        "current_order": ["zcode-free", "qoder", "cline", "workbuddy"],
        "recommended_order": ["qoder", "cline", "zcode-free", "workbuddy"],
        "reason": "qoder 实测 85 tok/s，上下文 128k 全绿，评定为【可当主力】"
    }
    print(format_feishu_approval_card(test_diff))
