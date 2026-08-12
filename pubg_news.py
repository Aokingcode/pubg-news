import requests
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# === 配置变量 ===

# 获取新闻语言列表
LANGUAGES = ["zh-cn", "zh-tw", "en", "ko"]

# 获取最新条数
SIZE = 10

# 推送通知使用的语言，不推送设置为空
LANG = "zh-cn"

# 推送排除标题中包含指定关键字的新闻
EXCLUDE_KEYWORDS = ["每周违规账号公示"]

# 邮件主题前缀（新闻标题将作为邮件主题推送）
MAIL_SUBJECT = "PUBG 新闻"

# 发件人 QQ 邮箱地址
# 如果上传 Github 请设置为空, 并在 Secrets 设置 QQ_MAIL_USER 变量
QQ_MAIL_USER = ""

# QQ 邮箱 SMTP 授权码（QQ 邮箱设置 -> 账户 -> 开启 SMTP 服务后生成, 不是 QQ 密码）
# 如果上传 Github 请设置为空, 并在 Secrets 设置 QQ_MAIL_AUTH_CODE 变量
QQ_MAIL_AUTH_CODE = ""

# 收件人邮箱地址, 可与发件人相同
# 如果上传 Github 请设置为空, 并在 Secrets 设置 QQ_MAIL_TO 变量
QQ_MAIL_TO = ""

# === 配置段结束 ===

SIZE = min(SIZE, 50)  # 上限 50
# 环境变量配置优先
QQ_MAIL_USER = (os.getenv("QQ_MAIL_USER") or QQ_MAIL_USER).strip()
QQ_MAIL_AUTH_CODE = os.getenv("QQ_MAIL_AUTH_CODE") or QQ_MAIL_AUTH_CODE
QQ_MAIL_TO = (os.getenv("QQ_MAIL_TO") or QQ_MAIL_TO).strip()

def fetch_news(lang):
    api_url = f"https://api-foc.krafton.com/content/post/news?lang={lang}&displayLocationType=NORMAL&size={SIZE}&page=1"
    headers = {
        "Origin": "https://pubg.com",
        "Referer": "https://pubg.com/",
        "Service-Game": "pubg",
        "Service-Lang": lang,
        "Service-Namespace": "PUBG_OFFICIAL",
        "Service-Url": f"https://pubg.com/{lang}/news"
    }

    res = requests.get(api_url, headers=headers)
    res.raise_for_status()
    posts = res.json().get("_embedded", {}).get("post", [])

    news_items = []
    for post in posts:
        images = post.get("images") or []
        if images:
            image_url = images[0].get("imageUrl", "")
            thumb_url = images[0].get("thumbUrl", "")
        else:
            image_url = ""
            thumb_url = ""

        news_items.append({
        "title": post["title"],
        "summary": post.get("summary", ""),
        "postId": post["postId"],
        "category": post.get("category", ""),
        "labels": post.get("labels", []),
        "createdAt": post.get("createdAt", ""),
        "displayTime": post.get("displayStartTime", ""),
        "imageUrl": image_url,
        "thumbUrl": thumb_url,
        "newsUrl": f"https://pubg.com/{lang}/news/{post['postId']}"
    })

    return news_items[:SIZE]

def load_existing(lang):
    filename = f"news_{lang}.json"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_news(lang, news_items):
    filename = f"news_{lang}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(news_items, f, ensure_ascii=False, indent=4)
    print(f"保存 {filename}，共 {len(news_items)} 条新闻。")

def merge_news(existing, new):
    existing_map = {item["postId"]: item for item in existing}
    for item in new:
        existing_map[item["postId"]] = item

    merged = list(existing_map.values())
    # 按 displayTime 降序排序
    merged.sort(key=lambda x: x.get("displayTime", ""), reverse=True)
    return merged[:SIZE]

def send_mail_notification(title, body, url):
    try:
        subject = f"{MAIL_SUBJECT}：{title}"

        html_parts = [f"<h3>{title}</h3>"]
        if body:
            html_parts.append(f"<p>{body}</p>")
        html_parts.append(f'<p><a href="{url}">查看原文</a></p>')

        msg = MIMEText("".join(html_parts), "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = QQ_MAIL_USER
        msg["To"] = QQ_MAIL_TO

        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(QQ_MAIL_USER, QQ_MAIL_AUTH_CODE)
            server.sendmail(QQ_MAIL_USER, [QQ_MAIL_TO], msg.as_string())
        print(f"✅ 邮件推送完成: {title} / {body}")
    except Exception as e:
        print(f"❌ 邮件推送失败: {e}")

def push(existing, new):
    if not QQ_MAIL_USER or not QQ_MAIL_AUTH_CODE or not QQ_MAIL_TO or not LANG:
        print("未配置推送。")
        return
    # 已保存的最后时间
    latest_time = existing[0].get("displayTime", "") if existing else ""
    # 已保存的 id 集合
    existing_ids = {item["postId"] for item in existing}

    # 根据时间升序
    new.sort(key=lambda x: x.get("displayTime", ""), reverse=False)

    for item in new:
        # 已保存的不推送
        if item["postId"] in existing_ids: continue
        # 时间早于已保存的不推送
        if item["displayTime"] < latest_time: continue
        # 包含排除关键字的不推送
        if any(keyword in item["title"] for keyword in EXCLUDE_KEYWORDS):
            continue
                
        send_mail_notification(item["title"], item["summary"], item["newsUrl"])

def main():
    for lang in LANGUAGES:
        existing_news = load_existing(lang)
        new_news = fetch_news(lang)
        merged_news = merge_news(existing_news, new_news)
        save_news(lang, merged_news)

        if lang == LANG:
            push(existing_news, new_news)



if __name__ == "__main__":
    main()
