import os
from datetime import datetime

import pandas as pd
import yfinance as yf

import smtplib
from email.mime.text import MIMEText
# --- 通知テンプレ（A/B/C） ---
PROMPT_A = """[A: 買い] 結論: {size}
理由: {reason}
参考: RSI14={rsi14:.1f}, MA20={ma20:.2f}, Close={last:.2f}
アクション: 指値/成行の目安や分割案を提示して
"""

PROMPT_B = """[B: 買い増し/様子見] 結論: {size}
理由: {reason}
参考: RSI14={rsi14:.1f}, MA20={ma20:.2f}, Close={last:.2f}
アクション: 買い増しなら分割、様子見なら条件を提示して
"""

PROMPT_C = """[C: 利益確定優先] 結論: {size}
理由: {reason}
参考: RSI14={rsi14:.1f}, MA20={ma20:.2f}, Close={last:.2f}
アクション: 一部利確/全利確の割合案を提示して
"""

# --- Gmail送信（前に成功した送信処理） ---
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


# --- 指標計算 ---
def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def fetch_close(ticker: str, days: int = 180) -> pd.Series:
    df = yf.download(
        ticker,
        period=f"{days}d",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"No price data: {ticker}")
    return df["Close"]


# --- ③ 判定ロジック（ここが本体）---
def judge_signal(ticker: str) -> dict:
    close = fetch_close(ticker, 180)
    last = float(close.iloc[-1])

    ma20 = float(close.rolling(20).mean().iloc[-1])
    rsi14 = float(calc_rsi(close, 14).iloc[-1])

    # 利益確定優先：過熱＋失速でSELL強
    if rsi14 >= 70 and last < ma20:
        level = "SELL_STRONG"
        size = "多め（部分利確30〜50%目安）"
    # 売られすぎ＋反転確認でBUY強
    elif rsi14 <= 30 and last > ma20:
        level = "BUY_STRONG"
        size = "やや多め（ただし分割で）"
    # 弱いシグナル（保守的）
    elif rsi14 >= 65 and last < ma20:
        level = "SELL"
        size = "少なめ（10〜30%目安）"
    elif rsi14 <= 35 and last > ma20:
        level = "BUY"
        size = "少なめ（様子見買い）"
    else:
        level = "HOLD"
        size = "-"

    reason = f"Close={last:.2f}, MA20={ma20:.2f}, RSI14={rsi14:.1f}"
    return {"ticker": ticker, "level": level, "size": size, "reason": reason}


def main():
    # 監視したい銘柄（例）
    tickers = {
        "SoftBank(9984.T)": "9984.T",
        "Tesla(TSLA)": "TSLA",
        "NVIDIA(NVDA)": "NVDA",
        "Supermicro(SMCI)": "SMCI",
        "Amazon(AMZN)": "AMZN",
        "Microsoft(MSFT)": "MSFT",
        "Advantest(6857.T)": "6857.T",
        "BYD(1211.HK)": "1211.HK",
        "Palantir(PLTR)": "PLTR",
        "Marvell(MRVL)": "MRVL",
        "Yaskawa(6506.T)": "6506.T",
        "Fujitsu(6702.T)": "6702.T",
    }

    results = []
    alerts = []

    for name, t in tickers.items():
        r = judge_signal(t)
        line = f"{name}: {r['level']} | {r['size']} | {r['reason']}"
        results.append(line)

        if r["level"] in ("SELL_STRONG", "SELL", "BUY_STRONG", "BUY"):
            alerts.append(line)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = "\n".join(
        [f"Time: {now}", "", "--- Alerts ---"]
        + (alerts if alerts else ["（該当なし）"])
        + ["", "--- All ---"]
        + results
    )

    # アラートがあるときだけ送る（必要ならここを変える）
    if alerts:
        send_mail(f"【株アラート】{len(alerts)}件", body)


if __name__ == "__main__":
    main()
