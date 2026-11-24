import os
import time
import akshare as ak
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# 1. 自動獲取全部港股通成分股名單（滬港通 + 深港通去重）
def get_all_southbound_tickers():
    tickers = set()
    try:
        # 獲取港股通即時行情表（包含所有港股通標的代碼）
        df_ggt = ak.stock_hk_ggt_components_em()
        if not df_ggt.empty and "代码" in df_ggt.columns:
            for code in df_ggt["代码"].astype(str):
                code_clean = code.strip().zfill(5)
                # yfinance 港股格式為 4 位數字 + .HK（若是 00700 則轉為 0700.HK）
                yf_code = f"{code_clean[-4:]}.HK" if code_clean.startswith("0") else f"{code_clean}.HK"
                tickers.add(yf_code)
    except Exception as e:
        print(f"AkShare 獲取港股通名單失敗，改用備用清單: {e}")

    # 若網路異常未能抓到名單，提供核心港股通標的作為備援
    if not tickers:
        tickers = {
            "0700.HK", "9988.HK", "3690.HK", "1810.HK", "0941.HK",
            "1211.HK", "2020.HK", "9880.HK", "9660.HK", "1686.HK",
            "0388.HK", "2318.HK", "3968.HK", "0883.HK", "1024.HK"
        }
    return sorted(list(tickers))

# 讀取可選的重點置頂股（若有設定 STOCK_LIST）
pinned_raw = os.environ.get("STOCK_LIST", "")
pinned_tickers = [t.strip().upper() for t in pinned_raw.split(",") if t.strip()]

all_tickers = get_all_southbound_tickers()
print(f"共載入 {len(all_tickers)} 隻港股通股份進行掃描...")

# 2. 批量下載日線數據並計算技術指標（分批下載避免請求過快）
results = []
batch_size = 50

for i in range(0, len(all_tickers), batch_size):
    batch = all_tickers[i:i + batch_size]
    try:
        data = yf.download(batch, period="4mo", interval="1d", group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print(f"批次下載異常: {e}")
        continue

    for ticker in batch:
        try:
            df = data[ticker] if len(batch) > 1 else data
            df = df.dropna(subset=["Close"])
            if df.empty or len(df) < 20:
                continue

            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]

            last_close = float(close.iloc[-1])
            prev_close = float(close.iloc[-2])
            if prev_close <= 0:
                continue
            pct_change = ((last_close - prev_close) / prev_close) * 100

            # 均線計算
            ma5 = float(close.rolling(5).mean().iloc[-1])
            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma60 = float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else ma20

            # 14 日 RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi14 = float((100 - (100 / (1 + rs))).iloc[-1])

            # 量比（今日成交量 / 過去 5 日均量）
            vol_today = float(volume.iloc[-1])
            vol_5d = float(volume.iloc[-6:-1].mean())
            vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1.0

            high_20d = float(high.tail(20).max())
            low_20d = float(low.tail(20).min())

            # 量化評分引擎
            score = 50
            signals = []

            if last_close > ma5 > ma20 > ma60:
                score += 25
                trend_status = "🚀 強勢多頭排列"
                signals.append("股價企穩主要均線之上，呈現標準多頭排列。")
            elif last_close > ma20 and ma20 > ma60:
                score += 15
                trend_status = "📈 中線上升趨勢"
                signals.append("股價守穩 20 天及 60 天線之上，中線趨勢向上。")
            elif last_close > ma20:
                score += 5
                trend_status = "🔄 站上月線反彈"
                signals.append("股價重上 20 天線，短線有轉強跡象。")
            elif last_close < ma20 and last_close < ma60:
                score -= 20
                trend_status = "⚠️ 空頭弱勢結構"
                signals.append("受壓於 20 天及 60 天線之下，走勢偏弱。")
            else:
                trend_status = "➖ 區間震盪整理"
                signals.append("均線交織，處於橫行整固階段。")

            if vol_ratio >= 1.5 and pct_change > 0:
                score += 15
                signals.append(f"放量上漲（量比 {vol_ratio:.2f}x），買盤資金積極。")
            elif vol_ratio >= 1.5 and pct_change < 0:
                score -= 15
                signals.append(f"放量下跌（量比 {vol_ratio:.2f}x），沽壓較重。")

            if rsi14 >= 75:
                score -= 5
                signals.append(f"RSI(14) 達 {rsi14:.1f}（超買區）。")
            elif rsi14 <= 30:
                score += 5
                signals.append(f"RSI(14) 跌至 {rsi14:.1f}（超賣區）。")

            score = max(0, min(100, score))

            results.append({
                "ticker": ticker,
                "is_pinned": ticker in pinned_tickers,
                "last_close": last_close,
                "pct_change": pct_change,
                "ma5": ma5,
                "ma20": ma20,
                "ma60": ma60,
                "rsi14": rsi14,
                "vol_ratio": vol_ratio,
                "high_20d": high_20d,
                "low_20d": low_20d,
                "score": score,
                "trend_status": trend_status,
                "signals": " ".join(signals)
            })
        except Exception:
            continue
    time.sleep(1)

# 3. 排序：置頂股優先，其餘按量化評分由高至低排序
results.sort(key=lambda x: (x["is_pinned"], x["score"], x["vol_ratio"]), reverse=True)

summary_rows = []
detail_cards = []

for idx, item in enumerate(results):
    color_class = "up" if item["pct_change"] > 0 else ("down" if item["pct_change"] < 0 else "flat")
    sign = "+" if item["pct_change"] > 0 else ""
    badge_class = "badge-bull" if item["score"] >= 70 else ("badge-bear" if item["score"] <= 40 else "badge-neutral")
    pin_tag = "⭐ " if item["is_pinned"] else ""

    summary_rows.append(f"""
    <tr>
      <td><strong>{pin_tag}{item['ticker']}</strong></td>
      <td>{item['last_close']:.2f}</td>
      <td class="{color_class}">{sign}{item['pct_change']:.2f}%</td>
      <td>{item['ma5']:.2f} / {item['ma20']:.2f} / {item['ma60']:.2f}</td>
      <td>{item['rsi14']:.1f}</td>
      <td>{item['vol_ratio']:.2f}x</td>
      <td><span class="badge {badge_class}">{item['score']} 分</span></td>
    </tr>
    """)

    # 為了保持網頁載入流暢，詳細診斷卡片只顯示「置頂股」與「評分 >= 75 分的強勢股」（最多前 30 隻）
    if item["is_pinned"] or (item["score"] >= 75 and idx < 30):
        detail_cards.append(f"""
        <div class="card">
          <div class="card-header">
            <h3>{pin_tag}{item['ticker']} ｜ {item['trend_status']}</h3>
            <span class="badge {badge_class}">量化評分：{item['score']} / 100</span>
          </div>
          <ul>
            <li><strong>技術面診斷：</strong>{item['signals']}</li>
            <li><strong>關鍵參考點位：</strong>20日阻力位 <code>{item['high_20d']:.2f}</code> ｜ 20日支撐位 <code>{item['low_20d']:.2f}</code> ｜ 月線(MA20) <code>{item['ma20']:.2f}</code></li>
          </ul>
        </div>
        """)

# 4. 生成網頁 (public/index.html)
os.makedirs("public", exist_ok=True)
hkt = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt).strftime("%Y-%m-%d %H:%M:%S HKT")

html_output = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>全市場港股通量化決策儀表盤</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif; background: #0b1120; color: #e2e8f0; max-width: 1100px; margin: 0 auto; padding: 24px; line-height: 1.6; }}
    h1 {{ color: #38bdf8; margin-bottom: 4px; }}
    .meta {{ color: #94a3b8; font-size: 0.9em; margin-bottom: 24px; }}
    .search-box {{ width: 100%; padding: 10px 14px; margin-bottom: 16px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #f8fafc; font-size: 1em; box-sizing: border-box; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #0f172a; color: #38bdf8; font-weight: 600; position: sticky; top: 0; }}
    .up {{ color: #22c55e; font-weight: bold; }}   /* 港股：綠升 */
    .down {{ color: #ef4444; font-weight: bold; }} /* 港股：紅跌 */
    .flat {{ color: #94a3b8; }}
    .card {{ background: #1e293b; border-left: 4px solid #38bdf8; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
    .card h3 {{ margin: 0; color: #f8fafc; }}
    .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; }}
    .badge-bull {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }}
    .badge-bear {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
    .badge-neutral {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid #64748b; }}
    code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin-bottom: 6px; }}
  </style>
</head>
<body>
  <h1>🇭🇰 全市場港股通量化掃描儀表盤</h1>
  <div class="meta">最後更新：{now_hkt} ｜ 已掃描港股通標的數：{len(results)} 隻 ｜ 配色規則：綠升紅跌</div>

  <h2>🔥 強勢多頭及重點置頂股診斷（評分 ≥ 75 分）</h2>
  {"".join(detail_cards) if detail_cards else "<p>今日暫無評分達 75 分以上的強勢多頭標的。</p>"}

  <h2>📊 全部港股通成分股量化總表（按評分高低排列）</h2>
  <input type="text" id="searchInput" class="search-box" onkeyup="filterTable()" placeholder="輸入股票代碼快速搜尋（例如：0700、9880、9660）...">
  <table id="stockTable">
    <thead>
      <tr>
        <th>代碼</th>
        <th>收盤價 (HKD)</th>
        <th>漲跌幅</th>
        <th>MA5 / MA20 / MA60</th>
        <th>RSI (14)</th>
        <th>量比</th>
        <th>趨勢評分</th>
      </tr>
    </thead>
    <tbody>
      {"".join(summary_rows)}
    </tbody>
  </table>

  <script>
    function filterTable() {{
      const filter = document.getElementById("searchInput").value.toUpperCase();
      const rows = document.getElementById("stockTable").getElementsByTagName("tr");
      for (let i = 1; i < rows.length; i++) {{
        const codeCell = rows[i].getElementsByTagName("td")[0];
        if (codeCell) {{
          const txt = codeCell.textContent || codeCell.innerText;
          rows[i].style.display = txt.toUpperCase().indexOf(filter) > -1 ? "" : "none";
        }}
      }}
    }}
  </script>
</body>
</html>
"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html_output)
