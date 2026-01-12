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

else:
    level = "HOLD"
    action = "様子見"

    # ① 今の「方向感」を一言で
    if abs(pct_vs_ma20) < 1.0:
        trend_msg = "最近の値動きはほぼ横ばい（方向がはっきりしない）"
    elif pct_vs_ma20 >= 1.0:
        trend_msg = "最近は上向き気味（ただし勢いが続くかは様子見）"
    else:
        trend_msg = "最近は下向き気味（ただし下げ止まるかは様子見）"

    # ② 「買いサイン」「売りサイン」が揃ってない理由を平易に
    reasons = []

    # 売りの理由：過熱 + 崩れ
    if rsi14 < SELL_RSI:
        reasons.append("売り：まだ『買われ過ぎ』の水準ではない（高値圏の過熱サインが弱い）")
    if last >= ma20:
        reasons.append("売り：値段がまだ大きく崩れていない（下落に転じたとは言い切れない）")

    # 買いの理由：売られ過ぎ + 反発
    if rsi14 > BUY_RSI:
        reasons.append("買い：まだ『売られ過ぎ』の水準ではない（安値圏とは言い切れない）")
    if last <= ma20:
        reasons.append("買い：反発が弱い（上向きに戻ったとは言い切れない）")

    # ③ 次にどうなったら動くか（目安）
    next_steps = (
        f"目安：\n"
        f"・買い増し候補 → 『安すぎサイン』が出たうえで、価格が上向きに戻る\n"
        f"・利益確定候補 → 『過熱サイン』が出たうえで、価格が下向きに崩れる\n"
        f"(参考値: RSIは買い={BUY_RSI}以下、売り={SELL_RSI}以上を目安)"
    )

    # ④ まとめ（数字は“参考”として最後に小さく）
    reason = (
        f"{trend_msg}\n"
        f"今回は『買い』も『売り』も決め手が不足しているため様子見です。\n"
        f"理由：\n- " + "\n- ".join(reasons) + "\n\n"
        f"{next_steps}\n\n"
        f"参考データ：終値={last:.2f}, MA20={ma20:.2f}（MA20比{pct_vs_ma20:.2f}%）, RSI14={rsi14:.1f}"
    )


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

