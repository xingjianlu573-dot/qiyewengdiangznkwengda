# -*- coding: utf-8 -*-
"""API 冒烟验证：健康检查 / 文档列表 / 四类问题 / 库外拒答 / 上传与删除。

用法：python scripts/api_smoke_test.py [base_url]
"""
import json
import os
import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def p(name: str, ok: bool, detail: str = "") -> None:
    print(("  ✓ " if ok else "  ✗ ") + name + (f" | {detail}" if detail else ""))


def main() -> int:
    print("=== API 冒烟验证 ===")

    # 1. 健康检查
    r = requests.get(f"{BASE}/api/health", timeout=10)
    data = r.json()
    p("健康检查 200", r.status_code == 200)
    p("知识库 4 文档 / 片段 ≥ 29（随解析粒度浮动）",
      data["stats"]["doc_count"] == 4 and data["stats"]["chunk_count"] >= 29,
      f"实际 {data['stats']['doc_count']} 文档 / {data['stats']['chunk_count']} 片段")
    p("三种格式齐全", data["stats"]["by_format"].get("PDF") == 1
      and data["stats"]["by_format"].get("Word") == 1
      and data["stats"]["by_format"].get("Markdown") == 2)

    # 2. 文档列表（中文文件名正确性）
    r = requests.get(f"{BASE}/api/documents", timeout=10)
    docs = r.json()["documents"]
    names = [d["name"] for d in docs]
    p("文档名中文正确", "网络故障SOP" in names[0], f"{names[0]}")
    p("文档名含 Windows", "Windows" in names[1], names[1])

    # 3. 四类典型问题
    cases = [
        ("电脑蓝屏代码 0x0000007B 怎么处理", "02-Windows故障处理.md"),
        ("公司网络突然断网，应该按什么顺序排查", "01-网络故障SOP.md"),
        ("VPN 提示认证失败怎么办", "03-VPN配置.docx"),
        ("Outlook 收不到邮件怎么排查", "04-邮箱问题.pdf"),
    ]
    for query, expect in cases:
        r = requests.post(f"{BASE}/api/query", json={"query": query}, timeout=30)
        resp = r.json()
        hit = expect in [c["doc_name"] for c in resp["citations"]]
        p(f"「{query[:18]}…」→ {expect}", r.status_code == 200 and hit and resp["grounded"],
          f"citations={[c['doc_name'] for c in resp['citations']]}")
        if resp["citations"]:
            c0 = resp["citations"][0]
            p("  引用含章节/匹配度元数据", bool(c0["section"]) and c0["score"] > 0)

    # 4. 库外问题拒答（幻觉抑制）
    r = requests.post(f"{BASE}/api/query", json={"query": "怎么申请年假和报销差旅费"}, timeout=30)
    resp = r.json()
    p("库外问题 grounded=False", r.status_code == 200 and not resp["grounded"],
      f"grounded={resp.get('grounded')}")
    p("拒答文案含『没有找到』", "没有找到" in resp["answer"], resp["answer"][:40])

    # 5. 上传新文档（临时 md）→ 入库 → 删除
    tmp_md = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "uploads", "_smoke_test.md")
    os.makedirs(os.path.dirname(tmp_md), exist_ok=True)
    with open(tmp_md, "w", encoding="utf-8") as f:
        f.write("# 服务器机房巡检规范\n\n## 巡检频率\n机房每日巡检一次，温度 18-27 摄氏度，湿度 40%-60%。\n\n## 巡检项\n检查 UPS 状态、空调运行、服务器指示灯、网络设备告警。")
    with open(tmp_md, "rb") as f:
        r = requests.post(f"{BASE}/api/documents", files={"file": ("机房巡检规范.md", f, "text/markdown")}, timeout=30)
    up = r.json()
    p("上传 .md 入库成功", r.status_code == 200 and up.get("doc_id"), f"{up.get('message','')}")
    doc_id = up.get("doc_id", "")
    if doc_id:
        r = requests.post(f"{BASE}/api/query", json={"query": "机房温湿度标准是多少"}, timeout=30)
        resp = r.json()
        p("新文档可被检索回答", resp["grounded"] and any("巡检" in c["doc_name"] for c in resp["citations"]),
          f"citations={[c['doc_name'] for c in resp['citations']]}")
        r = requests.delete(f"{BASE}/api/documents/{doc_id}", timeout=10)
        p("上传文档可删除", r.status_code == 200)
    os.remove(tmp_md)

    # 6. 非法格式拦截
    with open(tmp_md + ".exe", "wb") as f:
        f.write(b"MZ....")
    with open(tmp_md + ".exe", "rb") as f:
        r = requests.post(f"{BASE}/api/documents", files={"file": ("恶意.exe", f, "application/octet-stream")}, timeout=10)
    p("非白名单格式被拦截(415)", r.status_code == 415, f"status={r.status_code}")
    os.remove(tmp_md + ".exe")

    # 7. 最终状态回查
    r = requests.get(f"{BASE}/api/health", timeout=10)
    p("上传/删除后索引恢复 4 文档", r.json()["stats"]["doc_count"] == 4,
      f"实际 {r.json()['stats']['doc_count']}")

    print("=== 验证完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
