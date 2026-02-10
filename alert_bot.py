import os
VERSION = "v2026-01-12-01"
print("RUNNING VERSION:", VERSION)
import requests
from datetime import timedelta

import pandas as pd
import yfinance as yf

import smtplib
from email.mime.text import MIMEText

# ========= ニュース取得設定 =========
def fetch_company_news(ticker: str) -> dict:
    """
    戻り値:
      {
        "score": -1.0〜+1.0 の目安（ネガ〜ポジ）,
        "summary": "素人向けの一言",
        "headlines": ["見出し1", "見出し2", ...]
      }
    """
    if os.environ.get("USE_NEWS", "0") != "1":
        return {"score": 0.0, "summary": "個別ニュース: OFF", "headlines": []}

    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        return {"score": 0.0, "summary": "個別ニュース: APIキー未設定", "headlines": []}

    lookback_h = int(os.environ.get("NEWS_LOOKBACK_HOURS", "72"))
    limit = int(os.environ.get("NEWS_LIMIT", "20"))
    time_from = (datetime.utcnow() - timedelta(hours=lookback_h)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ここは使うニュースAPIに合わせてURL/paramsを調整する
    # 例：queryに ticker を入れる / from を入れる / limit を入れる など
    url = "https://example-news-api.com/query"
    params = {
        "q": ticker,
        "from": time_from,
        "limit": limit,
        "apikey": api_key,
        "lang": "en",  # 日本語も欲しければ "ja" or 両方
    }

    try:
        r = requests.get(url, params=params, timeout=25)
        data = r.json()
    except Exception as e:
        return {"score": 0.0, "summary": f"個別ニュース: 取得失敗（{e}）", "headlines": []}

    # --- 返却データの取り出し（APIによりフィールド名は違う） ---
    # 例：data["articles"] の中に title と sentiment がある想定
    articles = data.get("articles", []) or []

    headlines = []
    scores = []
    for a in articles[:limit]:
        title = a.get("title") or ""
        if title:
            headlines.append(title.strip())

        s = a.get("sentiment_score")  # APIによっては無い（その場合は後で別方法に）
        if s is not None:
            try:
                scores.append(float(s))
            except Exception:
                pass

    avg = sum(scores) / len(scores) if scores else 0.0

    if avg <= -0.15:
        mood = "逆風（悪材料多め）"
        hint = "→ 買うなら少額・分割、深追い注意"
    elif avg >= 0.15:
        mood = "追い風（好材料多め）"
        hint = "→ 攻めやすいが買い過ぎ注意"
    else:
        mood = "中立（強弱まちまち）"
        hint = "→ テクニカル重視でOK"

    summary = f"個別ニュース: {mood} / 平均={avg:+.2f} {hint}"
    top3 = headlines[:3]

    return {"score": avg, "summary": summary, "headlines": top3}

def judge_signal(ticker: str, news_info: dict | None = None) -> dict:
    ...
    # 既存の reason を作ったあとに
    if news_info:
        # 見出しは3件だけ表示（長くなりすぎないように）
        heads = news_info.get("headlines", [])
        heads_txt = "\n".join([f"  ・{h}" for h in heads]) if heads else "  ・（見出しなし）"
        reason = (
            reason
            + "\n\n"
            + news_info.get("summary", "個別ニュース: -")
            + "\n主な見出し:\n"
            + heads_txt
        )

    return {"ticker": ticker, "level": level, "action": action, "reason": reason}
    
# ========= メール送信設定 =========
def send_mail(subject: str, body: str) -> None:
    user = os.environ["GMAIL_USER"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("MAIL_TO", user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, app_pw)
        s.send_message(msg)


# ========= RSI計算 =========
def calc_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


# ========= 株価データ取得 =========
def fetch_close(ticker: str, days: int = 120) -> pd.Series:
    df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No price data for {ticker}")
    return df["Close"]


# ========= シグナル判定（攻め姿勢＋わかりやすい理由） =========
def judge_signal(ticker: str) -> dict:
    BUY_RSI = 40
    SELL_RSI = 75

# --- 追加：トレンド/変化を見込む指標 ---
    ma50 = float(close.rolling(50).mean().iloc[-1])

    # 20日(約1か月)/60日(約3か月) 変化率
    ret_20 = (last / float(close.iloc[-21]) - 1.0) * 100.0 if len(close) > 21 else 0.0
    ret_60 = (last / float(close.iloc[-61]) - 1.0) * 100.0 if len(close) > 61 else 0.0

    # 直近60日高値からの下落率（押し目の深さ）
    high_60 = float(close.iloc[-60:].max()) if len(close) >= 60 else float(close.max())
    drawdown_60 = (last / high_60 - 1.0) * 100.0  # マイナスなら高値から下落中

    # --- 判定 ---
    if rsi14 <= 30:
        level = "BUY_STRONG"
        action = "買い増し候補（分割で）"
        reason = (
            f"売られすぎ(RSI={rsi14:.1f})。短期で下がりすぎており、"
            f"反発の可能性あり（MA20比 {pct_vs_ma20:+.1f}%）。"
        )
    elif rsi14 <= BUY_RSI:
        level = "BUY"
        action = "少額で買い増し（攻め）"
        reason = (
            f"やや売られ気味(RSI={rsi14:.1f})。"
            f"下落の勢いが落ち着いてきたため、"
            f"少額でエントリーを検討（MA20比 {pct_vs_ma20:+.1f}%）。"
        )
    elif pct_vs_ma20 <= -2:
        level = "BUY"
        action = "押し目買い（少額）"
        reason = (
            f"株価が20日平均より下({pct_vs_ma20:+.1f}%)。"
            f"押し目の可能性あり、少しずつ買うのが◎（RSI={rsi14:.1f}）。"
        )
    elif rsi14 >= SELL_RSI:
        level = "SELL_STRONG"
        action = "利益確定優先（分割で）"
        reason = (
            f"買われすぎ(RSI={rsi14:.1f})。"
            f"短期的に上がりすぎなので一部利確を検討（MA20比 {pct_vs_ma20:+.1f}%）。"
        )
    else:
        level = "HOLD"
        action = "様子見"

        # HOLD理由をわかりやすく説明
        if abs(pct_vs_ma20) < 1.0:
            trend_msg = "最近の値動きは横ばい。方向感がまだ出ていません。"
        elif pct_vs_ma20 >= 1.0:
            trend_msg = "やや上向き傾向ですが、勢いが続くかは不明です。"
        else:
            trend_msg = "下向き気味ですが、底打ちの兆候はまだ弱いです。"

        reason = (
            f"{trend_msg}\n"
            f"買い・売りどちらの明確なサインも出ていないため、少し様子を見ましょう。\n"
            f"（RSI={rsi14:.1f}, MA20比={pct_vs_ma20:+.1f}%）"
        )

    return {"ticker": ticker, "level": level, "action": action, "reason": reason}


# ========= 対象銘柄取得 =========
def parse_tickers() -> list[str]:
    raw = os.environ.get("TICKERS", "AAPL")
    parts = [p.strip() for p in raw.replace("\n", " ").replace(",", " ").split(" ") if p.strip()]
    return parts


# ========= メイン処理 =========
def main() -> None:
    tickers = parse_tickers()
    results = []
    alerts = []

    for t in tickers:
        try:
            r = judge_signal(t)
        except Exception as e:
            r = {"ticker": t, "level": "ERROR", "action": "-", "reason": str(e)}
        results.append(r)
        if r["level"] in ("SELL_STRONG", "BUY_STRONG"):
            alerts.append(r)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"{r['ticker']} | {r['level']} | {r.get('action','')} | {r.get('reason','')}" for r in results]
    body = f"Time: {now}\n\n" + "\n".join(lines)

    always_send = os.environ.get("ALWAYS_SEND", "0") == "1"

    if alerts or always_send:
        subject = f"stock-alert-mailer {VERSION} {'ALERT' if alerts else 'TEST'} {now}"
        send_mail(subject, body)


# ========= 実行部分 =========
def debug_print_one(ticker: str) -> None:
    r = judge_signal(ticker)
    print("=== DEBUG RESULT ===")
    for k, v in r.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    # デバッグ：Actionsログに出す（メール不要）
    if os.environ.get("DEBUG_ONLY", "0") == "1":
        t = os.environ.get("DEBUG_TICKER", "TSM")
        debug_print_one(t)

    # テストメール（SMTP成功だけ確認）
    elif os.environ.get("SUCCESS_TEST", "0") == "1":
        send_mail("stock-alert-mailer ✅ TEST", "This is a success-path test mail.")

    # 通常運転（株価判定→必要ならメール送信）
    else:
        main()