import os
from datetime import datetime

import pandas as pd
import yfinance as yf

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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, app_pw)
        s.send_message(msg)


def calc_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def fetch_close(ticker: str, days: int = 120) -> pd.Series:
    df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"No price data for {ticker}")
    return df["Close"]

def judge_signal(ticker: str) -> dict:
    close = fetch_close(ticker, 120)

    last = float(close.iloc[-1])
    ma20 = float(close.rolling(20).mean().iloc[-1])
    rsi14 = float(calc_rsi(close, 14))

    # 判定条件（必要ならここだけ数値を変えればOK）
    SELL_RSI = 70
    BUY_RSI  = 30

    # どれだけ条件から離れているか（HOLD理由で使う）
    rsi_to_sell = SELL_RSI - rsi14   # <=0 なら売りRSI条件達成
    rsi_to_buy  = rsi14 - BUY_RSI    # <=0 なら買いRSI条件達成
    pct_vs_ma20 = (last / ma20 - 1.0) * 100.0 if ma20 != 0 else 0.0

    # SELL_STRONG
    if (rsi14 >= SELL_RSI) and (last < ma20):
        level = "SELL_STRONG"
        action = "利益確定優先（分割で）"
        reason = (
            f"RSI14={rsi14:.1f}が{SELL_RSI}以上（過熱気味）かつ、"
            f"終値={last:.2f}がMA20={ma20:.2f}を下回り（MA20比{pct_vs_ma20:.2f}%）→ 売り条件一致"
        )

    # BUY_STRONG
    elif (rsi14 <= BUY_RSI) and (last > ma20):
        level = "BUY_STRONG"
        action = "買い増し候補（分割で）"
        reason = (
            f"RSI14={rsi14:.1f}が{BUY_RSI}以下（売られ過ぎ）かつ、"
            f"終値={last:.2f}がMA20={ma20:.2f}を上回り（MA20比{pct_vs_ma20:.2f}%）→ 買い条件一致"
        )

    # HOLD（ここが今回のポイント）
    else:
        level = "HOLD"
        action = "様子見"

        hold_parts = []
        # 売り側が成立しない理由
        if rsi14 < SELL_RSI:
            hold_parts.append(f"売り未達：RSIが{SELL_RSI}未満（あと{rsi_to_sell:.1f}）")
        if last >= ma20:
            hold_parts.append(f"売り未達：終値がMA20以上（MA20比{pct_vs_ma20:.2f}%）")

        # 買い側が成立しない理由
        if rsi14 > BUY_RSI:
            hold_parts.append(f"買い未達：RSIが{BUY_RSI}超（あと{rsi_to_buy:.1f}）")
        if last <= ma20:
            hold_parts.append(f"買い未達：終値がMA20以下（MA20比{pct_vs_ma20:.2f}%）")

        # “次にどうなったら”も付ける
        reason = (
            f"RSI14={rsi14:.1f}, 終値={last:.2f}, MA20={ma20:.2f}（MA20比{pct_vs_ma20:.2f}%）\n"
            f"理由：{' / '.join(hold_parts)}\n"
            f"目安：SELLは RSI≥{SELL_RSI} かつ 終値<MA20、BUYは RSI≤{BUY_RSI} かつ 終値>MA20"
        )

    return {
        "ticker": ticker,
        "level": level,
        "action": action,
        "reason": reason,
        "close": last,
        "ma20": ma20,
        "rsi14": rsi14,
    }


def parse_tickers() -> list[str]:
    raw = os.environ.get("TICKERS", "AAPL")
    parts = [p.strip() for p in raw.replace("\n", " ").replace(",", " ").split(" ") if p.strip()]
    return parts


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

    # ★テスト用：ALWAYS_SEND=1 のときはアラート無しでも送る
    always_send = os.environ.get("ALWAYS_SEND", "0") == "1"

    if alerts or always_send:
        subject = f"stock-alert-mailer {'ALERT' if alerts else 'TEST'} {now}"
        send_mail(subject, body)

if __name__ == "__main__":
    # テストメールだけ送信したいとき
    if os.environ.get("SUCCESS_TEST", "0") == "1":
        send_mail("stock-alert-mailer ✅ TEST", "This is a success-path test mail.")
    else:
        main()

