import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone

import yfinance as yf

# ---- mail ----
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO = os.environ.get("MAIL_TO", GMAIL_USER)

def send_mail(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = TO
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.ehlo()
        s.starttls()
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.send_message(msg)

# ---- signal utils ----
def rsi(series, period: int = 14):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    rs = up / down
    return 100 - (100 / (1 + rs))

def fetch_close(ticker: str, days: int = 120):
    df = yf.download(ticker, period=f"{days}d", interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"no data: {ticker}")
    return df["Close"]

def tech_signal(close):
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    last = close.iloc[-1]
    r = rsi(close).iloc[-1]

    # ざっくり初期ルール（あとで調整）
    if r >= 70 and last < ma20:
        return "SELL_CANDIDATE", r, last, ma20, ma50
    if r <= 30 and last > ma20:
        return "BUY_CANDIDATE", r, last, ma20, ma50
    if last > ma20 > ma50:
        return "UP_TREND", r, last, ma20, ma50
    if last < ma20 < ma50:
        return "DOWN_TREND", r, last, ma20, ma50
    return "HOLD", r, last, ma20, ma50

def market_risk():
    # 地合い指標（超シンプル版）
    # NASDAQ: ^IXIC / S&P: ^GSPC / VIX: ^VIX / USDJPY: JPY=X / 米10年金利: ^TNX
    ixic = fetch_close("^IXIC", 120)
    vix = fetch_close("^VIX", 120)
    tnx = fetch_close("^TNX", 120)

    ixic_ma20 = ixic.rolling(20).mean().iloc[-1]
    ixic_last = ixic.iloc[-1]
    vix_last = vix.iloc[-1]
    tnx_last = tnx.iloc[-1]

    risk = 0
    if ixic_last < ixic_ma20:  # ナスが20MA下
        risk += 1
    if vix_last >= 20:        # VIX高め
        risk += 1
    if tnx_last >= 45:        # 10年金利(=^TNX)が高め（目安）
        risk += 1

    return risk, ixic_last, vix_last, tnx_last

def main():
    # 保有銘柄（必要なら後で変更）
    tickers = {
        "SoftBank(9984.T)": "9984.T",
        "Tesla(TSLA)": "TSLA",
        "NVIDIA(NVDA)": "NVDA",
        "Supermicro(SMCI)": "SMCI",
        "Amazon(AMZN)": "AMZN",
        "Microsoft(MSFT)": "MSFT",
        "Advantest(6857.T)": "6857.T",
        "BYD(1211.HK)": "1211.HK",
    }

    risk, ixic_last, vix_last, tnx_last = market_risk()

    lines = []
    alerts = []
    for name, t in tickers.items():
        close = fetch_close(t, 120)
        sig, r, last, ma20, ma50 = tech_signal(close)

        line = f"{name}: {sig} | RSI {r:.1f} | Close {last:.2f} | MA20 {ma20:.2f} | MA50 {ma50:.2f}"
        lines.append(line)

        # アラート条件（初期：売り/買い候補だけ通知）
        if sig in ("SELL_CANDIDATE", "BUY_CANDIDATE"):
            alerts.append(line)

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    header = [
        f"Time: {now}",
        f"Market risk score: {risk} (NASDAQ {ixic_last:.0f}, VIX {vix_last:.1f}, US10Y(^TNX) {tnx_last:.1f})",
        "",
    ]

    if alerts:
        subject = f"【株アラート】売買候補 {len(alerts)}件 / risk={risk}"
        body = "\n".join(header + ["--- Alerts ---"] + alerts + ["", "--- All ---"] + lines)
        send_mail(subject, body)
    else:
        # 無駄通知を減らすため、通常は送らない（欲しければここを送るに変更OK）
        pass

if __name__ == "__main__":
    main()
