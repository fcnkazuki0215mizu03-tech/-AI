import os
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- Gmail送信（前に成功した送信処理） ---
import smtplib
from email.mime.text import MIMEText

def send_mail(subject: str, body: str) -> None:
    user = os.environ["GMAIL_USER"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("MAIL_TO", user)

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    # 465(SSL)で送る版（あなたの環境で成功しているならこれでOK）
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

def fetch_close(ticker: str, days: int = 120) -> pd.Series:
    df = yf.download(ticker, period=f"{days}d", interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No price data: {ticker}")
    return df["Close"]

def judge_signal(ticker: str) -> dict:
    close = fetch_close(ticker, 120)
    last = float(close.iloc[-1])

    ma20 = float(close.rolling(20).mean().iloc[-1])
    rsi14 = float(calc_rsi(close, 14).iloc[-1])

    # --- ここが「利益確定優先」の判定 ---
    # SELL強：過熱（RSI>=70）＋失速（終値がMA20割れ）
    if rsi14 >= 70 and last < ma20:
        level = "SELL_STRONG"
        action = "利益確定優先（部分利確30〜50%目安）"
    # BUY強：売られすぎ（RSI<=30）＋反転確認（終値がMA20超え）
    elif rsi14 <= 30 and last > ma20:
        level = "BUY_STRONG"
        action = "買い増し候補（分割で）"
    else:
        level = "HOLD"
        action = "様子見"

    reason = f"Close={last:.2f}, MA20={ma20:.2f}, RSI14={rsi14:.1f}"
    return {"ticker": ticker, "level": level, "action": action, "reason": reason}

def main():
    # 監視銘柄（必要なら増やしてOK）
    tickers = {
        "SoftBank(9984.T)": "9984.T",
        "Advantest(6857.T)": "6857.T",
        "Yaskawa(6506.T)": "6506.T",
        "Fujitsu(6702.T)": "6702.T",
        "Tesla(TSLA)": "TSLA",
        "NVIDIA(NVDA)": "NVDA",
        "Supermicro(SMCI)": "SMCI",
        "Amazon(AMZN)": "AMZN",
        "Microsoft(MSFT)": "MSFT",
        "Palantir(PLTR)": "PLTR",
        "Marvell(MRVL)": "MRVL",
        "BYD(1211.HK)": "1211.HK",
    }

    results = []
    alerts = []

    for name, t in tickers.items():
        r = judge_signal(t)
        results.append(f"{name}: {r['level']} | {r['action']} | {r['reason']}")
        if r["level"] in ("SELL_STRONG", "BUY_STRONG"):
            alerts.append(f"{name}: {r['level']} | {r['action']} | {r['reason']}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = "\n".join([f"Time: {now}", "", "--- Alerts ---"] + (alerts if alerts else ["（該当なし）"]) + ["", "--- All ---"] + results)

    # アラートがある時だけメール（スパム防止の第一歩）
    if alerts:
        subject = f"【株アラート】{len(alerts)}件（BUY/SELL強）"
        send_mail(subject, body)

if __name__ == "__main__":
    main()
