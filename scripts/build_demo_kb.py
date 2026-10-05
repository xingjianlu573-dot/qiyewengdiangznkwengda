# -*- coding: utf-8 -*-
"""生成演示知识库中的 Word(.docx) 与 PDF 文档。

输出：
    data/knowledge_base/03-VPN配置.docx   （Word 格式示例）
    data/knowledge_base/04-邮箱问题.pdf    （PDF 格式示例）

用途：与 01-网络故障SOP.md / 02-Windows故障处理.md 一起构成
「IT 运维知识库」演示数据，覆盖 PDF / Word / Markdown 三种上传格式。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

VPN_CONTENT = [
    ("VPN 配置与故障排查手册", [
        ("1. 安装 VPN 客户端", [
            "从公司内网门户下载 VPN 客户端安装包（仅支持官方渠道，禁止使用第三方修改版）。",
            "安装时使用默认路径，安装完成后重启电脑。",
            "若安装过程中杀毒软件拦截，请选择「允许」，并将 VPN 客户端加入信任列表。",
        ]),
        ("2. 首次连接配置", [
            "打开 VPN 客户端，服务器地址填写公司提供的接入域名，例如 vpn.company.com。",
            "输入域账号（格式：工号@company.com）与密码。",
            "首次登录需完成双因素认证（MFA）：在手机认证 App（如 Microsoft Authenticator）上确认或输入动态验证码。",
            "勾选「自动连接」后保存配置。",
        ]),
        ("3. 常见错误处理", [
            "错误提示「认证失败」：确认密码正确、账号未被锁定；锁定需联系 IT 部门解锁或等待策略解锁时间。",
            "错误提示「无法连接到服务器」：检查本地网络是否正常、防火墙是否放行 VPN 端口（UDP 500/4500、TCP 443），尝试切换网络（有线/热点）后重试。",
            "连接成功但无法访问内网系统：检查是否开启了「按需路由」，尝试断开重连；仍不行则执行 ipconfig /flushdns 后重试。",
            "频繁掉线：检查网络稳定性，关闭省电模式对网卡的限制，联系 IT 检查网关会话超时策略。",
        ]),
        ("4. 安全注意事项", [
            "VPN 账号仅限本人使用，禁止共享。",
            "离开工位或使用公共网络时，务必断开 VPN 连接。",
            "长期出差员工建议申请「永久 VPN」策略，并配合 MFA 双重验证使用。",
            "遇到钓鱼邮件索取 VPN 密码，一律拒绝并向安全团队举报。",
        ]),
        ("5. 卸载与重装", [
            "控制面板 → 程序和功能 → 卸载 VPN 客户端。",
            "卸载后删除残留目录（默认 C:\\Program Files\\xxx），重新安装最新版本。",
            "重装后如仍提示配置异常，联系 IT 运维获取重置工具。",
        ]),
    ]),
]

MAIL_CONTENT = [
    "企业邮箱问题处理指南",
    "（适用于公司邮箱、Outlook 客户端与手机邮箱 App）",
    "",
    "一、Outlook 无法收发邮件",
    "1. 检查网络连接，确认可以正常访问网页。",
    "2. 查看 Outlook 右下角状态：显示“正在尝试连接”时，先退出并重启 Outlook。",
    "3. 仍然失败：控制面板 → 邮件 → 账户设置 → 修复账户（输入密码重新验证）。",
    "4. 确认服务器地址无误：收件服务器（IMAP：imap.company.com，端口 993，SSL）与发件服务器（SMTP：smtp.company.com，端口 465，SSL）。",
    "5. 检查杀毒软件是否拦截了 Outlook 的网络连接。",
    "",
    "二、密码错误或账号被锁定",
    "1. 连续输错密码会触发账号锁定，一般 30 分钟后自动解锁。",
    "2. 通过公司自助密码重置门户（SSPR）修改密码，修改后需重新在 Outlook 中输入新密码。",
    "3. 仍提示密码错误：联系 IT 部门验证身份后重置密码。",
    "",
    "三、邮件发送延迟或投递失败",
    "1. 查看发件箱中邮件是否停留在“未发送”，右键选择“发送/接收”。",
    "2. 收到退信（Nondelivery Report）：查看退信代码，常见为收件人地址错误或对方服务器拒收。",
    "3. 大批量发送（超过 50 封/次）会被系统拦截，需分批发或使用群发服务。",
    "",
    "四、附件大小超限",
    "1. 公司邮箱单封邮件附件上限 20MB。",
    "2. 大文件请使用公司内部网盘或文件共享服务，在邮件中附共享链接。",
    "3. 超大附件功能仅对部分部门开放，需提前申请。",
    "",
    "五、邮箱容量已满",
    "1. 邮箱容量上限 5GB，剩余空间低于 10% 时系统会发送提醒邮件。",
    "2. 清理方法：删除大附件邮件、清空已删除邮件文件夹、归档旧邮件到本地 PST。",
    "3. 清空后容量仍未恢复：等待 1 小时同步，或重启 Outlook。",
    "",
    "六、垃圾邮件与误拦截",
    "1. 重要邮件被误判为垃圾邮件：在 Outlook 中右键 → 标记为“非垃圾邮件”，并添加发件人到安全发件人列表。",
    "2. 收到可疑钓鱼邮件：不要点击链接，使用“举报钓鱼邮件”按钮上报安全团队。",
    "3. 公司邮件网关会拦截外部陌生发件人邮件，如需放行请联系 IT。",
    "",
    "七、手机端邮箱配置",
    "1. 建议使用公司推荐的手机邮箱 App，或系统自带邮件应用。",
    "2. 手动配置时使用 IMAP（993/SSL）与 SMTP（465/SSL），账号为完整邮箱地址。",
    "3. 配置后需开启“在服务器上保留邮件副本”，避免手机删除导致电脑端邮件丢失。",
    "",
    "八、离职员工邮箱处理",
    "1. 离职当天由 HR 发起邮箱回收流程，邮箱转为自动转发至交接人或部门公共邮箱。",
    "2. 离职后邮箱将无法登录，重要资料请在离职前归档。",
    "3. 未完成的工作邮件，可在离职前手动转发给交接同事。",
]


def build_docx(path: str) -> None:
    doc = Document()
    title = doc.add_heading(VPN_CONTENT[0][0], level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for section_title, paras in VPN_CONTENT[0][1]:
        doc.add_heading(section_title, level=1)
        for para in paras:
            p = doc.add_paragraph(para)
            p.paragraph_format.space_after = Pt(6)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc.save(path)
    print(f"[OK] 已生成 Word 文档：{path}")


def build_pdf(path: str) -> None:
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    margin = 50
    y = margin

    # 选择中文字体：优先系统字体，回退内置简体中文字体
    font_candidates = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyh.ttf",
    ]
    fontname, fontfile = None, None
    for fp in font_candidates:
        if os.path.exists(fp):
            fontfile = fp
            fontname = "cnfont"
            page.insert_font(fontname=fontname, fontfile=fp)
            break
    if fontname is None:
        fontname = "china-s"  # MuPDF 内置简体中文字体

    line_h = 15
    for line in MAIL_CONTENT:
        # 标题行加粗放大
        is_title = line.startswith("一、") or line.startswith("二、") or line.startswith("三、") \
            or line.startswith("四、") or line.startswith("五、") or line.startswith("六、") \
            or line.startswith("七、") or line.startswith("八、")
        is_main_title = line.startswith("企业邮箱")
        size = 16 if is_main_title else (13 if is_title else 10.5)
        if is_main_title:
            y += 6
        if y > 842 - margin - line_h:
            page = doc.new_page(width=595, height=842)
            y = margin
        page.insert_text((margin, y), line, fontsize=size, fontname=fontname)
        y += line_h + (4 if is_main_title else (2 if is_title else 0))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 字体子集化 + 压缩，避免整包嵌入中文字体导致文件过大
    doc.subset_fonts()
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print(f"[OK] 已生成 PDF 文档：{path}（字体：{fontname}）")


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "knowledge_base")
    build_docx(os.path.join(base, "03-VPN配置.docx"))
    build_pdf(os.path.join(base, "04-邮箱问题.pdf"))
