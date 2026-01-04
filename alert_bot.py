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
    last = float(close
