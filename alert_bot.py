import os
VERSION = "v2026-01-12-01"
print("RUNNING VERSION:", VERSION)
from datetime import datetime

import pandas as pd
import yfinance as yf

import smtplib
from email.mime.text import MIMEText


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

    close = fetch_close(ticker, 120)
    last = float(close.iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    rsi14 = float(calc_rsi(close, 14))

    pct_vs_ma20 = (last / ma20 - 1.0) * 100.0

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
if __name__ == "__main__":
    if os.environ.get("SUCCESS_TEST", "0") == "1":
        send_mail("stock-alert-mailer ✅ TEST", "This is a success-path test mail.")
    else:
        main()
