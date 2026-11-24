import os
import re
import time
import requests
import akshare as ak
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# 1. 多源獲取完整港股通成分股名單
def get_all_southbound_tickers():
    tickers = set()

    # 來源 A：港交所 (HKEX) 官方合資格股份名單
    hkex_urls = [
        "https://www.hkex.com.hk/chi/market/sec_tradinfo/stockconnect/EligibleStocks_c.htm",
        "https://www.hkex.com.hk/eng/market/sec_tradinfo/stockconnect/EligibleStocks.htm"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in hkex_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                codes = re.findall(r'\b0\d{4}\b', resp.text)
                for code in codes:
                    if code != "00000":
                        tickers.add(f"{code[-4:]}.HK")
                if len(tickers) > 300:
                    return sorted(list(tickers))
        except Exception:
            pass

    # 來源 B：AkShare 港股通成分股介面
    try:
        df_ggt = ak.stock_hk_ggt_components_em()
        if not df_ggt.empty and "代码" in df_ggt.columns:
            for code in df_ggt["代码"].astype(str):
                code_clean = code.strip().zfill(5)
                yf_code = f"{code_clean[-4:]}.HK" if code_clean.startswith("0") else f"{code_clean}.HK"
                tickers.add(yf_code)
            if len(tickers) > 300:
                return sorted(list(tickers))
    except Exception:
        pass

    # 來源 C：核心港股通保底清單（緊湊格式防止貼上截斷）
    raw_codes = (
        "0001,0002,0003,0005,0006,0011,0012,0016,0017,0019,0020,0027,0066,0101,0135,0144,0151,0168,0175,0177,"
        "0200,0241,0257,0267,0268,0270,0285,0288,0291,0293,0316,0322,0341,0354,0358,0384,0386,0388,0390,0425,"
        "0522,0551,0552,0570,0586,0590,0631,0656,0669,0683,0688,0694,0696,0700,0728,0753,0762,0763,0772,0780,"
        "0788,0817,0823,0836,0853,0857,0867,0868,0880,0881,0883,0902,0909,0914,0916,0921,0939,0941,0960,0966,"
        "0968,0981,0992,0998,1024,1038,1044,1055,1066,1070,1072,1088,1093,1099,1109,1113,1114,1128,1138,1157,"
        "1171,1177,1179,1186,1193,1199,1208,1209,1211,1288,1299,1308,1313,1316,1336,1339,1347,1357,1359,1368,"
        "1378,1385,1398,1415,1448,1478,1513,1530,1548,1579,1585,1658,1686,1698,1766,1772,1776,1787,1797,1800,"
        "1801,1810,1816,1818,1821,1833,1876,1877,1880,1882,1888,1898,1908,1910,1913,1918,1919,1928,1929,1951,"
        "1952,1972,1988,1997,1999,2007,2013,2015,2018,2020,2057,2076,2096,2099,2150,2162,2186,2196,2202,2208,"
        "2238,2252,2268,2269,2273,2276,2282,2285,2313,2318,2319,2328,2331,2333,2338,2357,2359,2367,2380,2382,"
        "2386,2388,2400,2423,2498,2518,2588,2600,2601,2602,2607,2611,2618,2628,2638,2688,2689,2800,2822,2823,"
        "2828,2858,2883,2888,2899,3032,3033,3311,3319,3320,3323,3328,3339,3347,3360,3380,3606,3613,3618,3668,"
        "3690,3692,3738,3759,3800,3808,3868,3888,3896,3898,3900,3908,3918,3931,3933,3958,3968,3988,3993,3996,"
        "3998,6030,6049,6055,6060,6066,6078,6082,6088,6098,6110,6160,6166,6185,6186,6608,6618,6682,6690,6699,"
        "6808,6818,6821,6823,6837,6855,6862,6865,6869,6881,6886,6963,6969,6979,6990,9618,9626,9633,9658,9660,"
        "9668,9688,9690,9696,9698,9863,9866,9868,9878,9880,9888,9896,9901,9911,9922,9923,9926,9959,9961,9969,"
        "9985,9987,9988,9992,9995,9996,9999"
    )
    for c in raw_codes.split(","):
        if c.strip():
            tickers.add(f"{c.strip()}.HK")
    return sorted(list(tickers))

# 2. 下載大市基準 (2800.HK 盈富基金)
bench_ret_20d = 0.0
bench_ret_60d = 0.0
try:
    bench_df = yf.download("2800.HK", period="4mo", interval="1d", progress=False, timeout=15)
    if isinstance(bench_df.columns, pd.MultiIndex):
        bench_df.columns = bench_df.columns.get_level_values(0)
    bench_close = bench_df["Close"].dropna()
    if len(bench_close) >= 21:
        bench_ret_20d = ((float(bench_close.iloc[-1]) - float(bench_close.iloc[-21])) / float(bench_close.iloc[-21])) * 100
    if len(bench_close) >= 61:
        bench_ret_60d = ((float(bench_close.iloc[-1]) - float(bench_close.iloc[-61])) / float(bench_close.iloc[-61])) * 100
except Exception as e:
    print(f"基準下載異常: {e}")

pinned_raw = os.environ.get("STOCK_LIST", "")
pinned_tickers = [t.strip().upper() for t in pinned_raw.split(",") if t.strip()]

all_tickers = sorted(list(set(get_all_southbound_tickers()) | set(pinned_tickers)))
print(f"共載入 {len(all_tickers)} 隻港股通股份，開始極速批量掃描...")

# 3. 分批下載日線數據並計算技術指標與 Relative Strength
results = []
batch_size = 100

for i in range(0, len(all_tickers), batch_size):
    batch = all_tickers[i:i + batch_size]
    try:
        data = yf.download(
            batch,
            period="4mo",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True,
            timeout=15
        )
    except Exception:
        continue

    if data is None or data.empty:
        continue

    for ticker in batch:
        try:
            df = data[ticker] if len(batch) > 1 else data
            df = df.dropna(subset=["Close"])
            if df.empty or len(df) < 21:
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

            ret_20d = ((last_close - float(close.iloc[-21])) / float(close.iloc[-21])) * 100
            ret_60d = ((last_close - float(close.iloc[-61])) / float(close.iloc[-61])) * 100 if len(close) >= 61 else ret_20d

            rs_diff_20d = ret_20d - bench_ret_20d
            rs_diff_60d = ret_60d - bench_ret_60d
            rs_weighted_excess = (rs_diff_20d * 0.6) + (rs_diff_60d * 0.4)

            ma5 = float(close.rolling(5).mean().iloc[-1])
            ma20 = float(close.rolling(20).mean().iloc[-1])
            ma60 = float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else ma20

            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi14 = float((100 - (100 / (1 + rs))).iloc[-1])

            vol_today = float(volume.iloc[-1])
            vol_5d = float(volume.iloc[-6:-1].mean())
            vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1.0

            high_20d = float(high.tail(20).max())
            low_20d = float(low.tail(20).min())

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
                "rs_diff_20d": rs_diff_20d,
                "rs_diff_60d": rs_diff_60d,
                "rs_weighted_excess": rs_weighted_excess
            })
        except Exception:
            continue
    time.sleep(0.5)

# 4. 計算全市場 RS Rating（1 至 99 百分位排名）與綜合評分
if results:
    rs_series = pd.Series([r["rs_weighted_excess"] for r in results])
    rs_ranks = (rs_series.rank(pct=True) * 98 + 1).round().astype(int).tolist()
else:
    rs_ranks = []

for item, rs_rating in zip(results, rs_ranks):
    item["rs_rating"] = rs_rating
    score = 50
    signals = []

    if item["last_close"] > item["ma5"] > item["ma20"] > item["ma60"]:
        score += 20
        trend_status = "🚀 強勢多頭排列"
        signals.append("股價企穩主要均線之上，呈現標準多頭排列。")
    elif item["last_close"] > item["ma20"] and item["ma20"] > item["ma60"]:
        score += 12
        trend_status = "📈 中線上升趨勢"
        signals.append("股價守穩 20 天及 60 天線之上，中線趨勢向上。")
    elif item["last_close"] > item["ma20"]:
        score += 5
        trend_status = "🔄 站上月線反彈"
        signals.append("股價重上 20 天線，短線有轉強跡象。")
    elif item["last_close"] < item["ma20"] and item["last_close"] < item["ma60"]:
        score -= 18
        trend_status = "⚠️ 空頭弱勢結構"
        signals.append("受壓於 20 天及 60 天線之下，走勢偏弱。")
    else:
        trend_status = "➖ 區間震盪整理"
        signals.append("均線交織，處於橫行整固階段。")

    if rs_rating >= 85:
        score += 15
        signals.append(f"相對強弱極強（RS Rating {rs_rating}，近20日跑贏大市 {item['rs_diff_20d']:+.1f}%）。")
    elif rs_rating >= 70:
        score += 8
        signals.append(f"相對強弱跑贏大市（RS Rating {rs_rating}，近20日超額 {item['rs_diff_20d']:+.1f}%）。")
    elif rs_rating <= 25:
        score -= 10
        signals.append(f"相對大市明顯偏弱（RS Rating {rs_rating}，近20日跑輸大市 {item['rs_diff_20d']:+.1f}%）。")

    if item["vol_ratio"] >= 1.5 and item["pct_change"] > 0:
        score += 12
        signals.append(f"放量上漲（量比 {item['vol_ratio']:.2f}x），買盤資金積極。")
    elif item["vol_ratio"] >= 1.5 and item["pct_change"] < 0:
        score -= 12
        signals.append(f"放量下跌（量比 {item['vol_ratio']:.2f}x），沽壓較重。")

    if item["rsi14"] >= 75:
        score -= 5
        signals.append(f"RSI(14) 達 {item['rsi14']:.1f}（超買區）。")
    elif item["rsi14"] <= 30:
        score += 5
        signals.append(f"RSI(14) 跌至 {item['rsi14']:.1f}（超賣區）。")

    item["score"] = max(0, min(100, score))
    item["trend_status"] = trend_status
    item["signals"] = " ".join(signals)

# 5. 排序與生成 HTML
results.sort(key=lambda x: (x["is_pinned"], x["score"], x["rs_rating"]), reverse=True)

summary_rows = []
detail_cards = []

for idx, item in enumerate(results):
    color_class = "up" if item["pct_change"] > 0 else ("down" if item["pct_change"] < 0 else "flat")
    sign = "+" if item["pct_change"] > 0 else ""

    rs_diff_class = "up" if item["rs_diff_20d"] > 0 else ("down" if item["rs_diff_20d"] < 0 else "flat")
    rs_sign = "+" if item["rs_diff_20d"] > 0 else ""

    rs_badge = "badge-bull" if item["rs_rating"] >= 80 else ("badge-bear" if item["rs_rating"] <= 30 else "badge-neutral")
    badge_class = "badge-bull" if item["score"] >= 70 else ("badge-bear" if item["score"] <= 40 else "badge-neutral")
    pin_tag = "⭐ " if item["is_pinned"] else ""

    summary_rows.append(f"""
    <tr>
      <td><strong>{pin_tag}{item['ticker']}</strong></td>
      <td>{item['last_close']:.2f}</td>
      <td class="{color_class}">{sign}{item['pct_change']:.2f}%</td>
      <td><span class="badge {rs_badge}">RS {item['rs_rating']}</span> <span class="{rs_diff_class}" style="font-size:0.85em;">({rs_sign}{item['rs_diff_20d']:.1f}%)</span></td>
      <td>{item['ma5']:.2f} / {item['ma20']:.2f} / {item['ma60']:.2f}</td>
      <td>{item['rsi14']:.1f}</td>
      <td>{item['vol_ratio']:.2f}x</td>
      <td><span class="badge {badge_class}">{item['score']} 分</span></td>
    </tr>
    """)

    if item["is_pinned"] or (item["score"] >= 75 and idx < 35):
        detail_cards.append(f"""
        <div class="card">
          <div class="card-header">
            <h3>{pin_tag}{item['ticker']} ｜ {item['trend_status']}</h3>
            <div>
              <span class="badge {rs_badge}" style="margin-right:6px;">RS Rating：{item['rs_rating']}</span>
              <span class="badge {badge_class}">綜合評分：{item['score']} / 100</span>
            </div>
          </div>
          <ul>
            <li><strong>技術面與強弱診斷：</strong>{item['signals']}</li>
            <li><strong>相對大市表現 (vs 2800.HK)：</strong>近20日超額報酬 <code class="{rs_diff_class}">{rs_sign}{item['rs_diff_20d']:.2f}%</code> ｜ 近60日超額報酬 <code>{item['rs_diff_60d']:+.2f}%</code></li>
            <li><strong>關鍵參考點位：</strong>20日阻力位 <code>{item['high_20d']:.2f}</code> ｜ 20日支撐位 <code>{item['low_20d']:.2f}</code> ｜ 月線(MA20) <code>{item['ma20']:.2f}</code></li>
          </ul>
        </div>
        """)

os.makedirs("public", exist_ok=True)
hkt = timezone(timedelta(hours=8))
now_hkt = datetime.now(hkt).strftime("%Y-%m-%d %H:%M:%S HKT")

html_output = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>全市場港股通量化決策儀表盤 (含 Relative Strength)</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif; background: #0b1120; color: #e2e8f0; max-width: 1180px; margin: 0 auto; padding: 24px; line-height: 1.6; }}
    h1 {{ color: #38bdf8; margin-bottom: 4px; }}
    .meta {{ color: #94a3b8; font-size: 0.9em; margin-bottom: 24px; }}
    .search-box {{ width: 100%; padding: 10px 14px; margin-bottom: 16px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #f8fafc; font-size: 1em; box-sizing: border-box; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; background: #1e293b; border-radius: 8px; overflow: hidden; font-size: 0.95em; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #0f172a; color: #38bdf8; font-weight: 600; position: sticky; top: 0; }}
    .up {{ color: #22c55e; font-weight: bold; }}
    .down {{ color: #ef4444; font-weight: bold; }}
    .flat {{ color: #94a3b8; }}
    .card {{ background: #1e293b; border-left: 4px solid #38bdf8; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }}
    .card h3 {{ margin: 0; color: #f8fafc; }}
    .badge {{ padding: 3px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; display: inline-block; }}
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
  <div class="meta">最後更新：{now_hkt} ｜ 已掃描港股通標的數：{len(results)} 隻 ｜ 基準 (2800.HK) 20日/60日表現：{bench_ret_20d:+.2f}% / {bench_ret_60d:+.2f}% ｜ 配色：綠升紅跌</div>

  <h2>🔥 強勢多頭及重點置頂股診斷（綜合評分 ≥ 75 分）</h2>
  {"".join(detail_cards) if detail_cards else "<p>今日暫無綜合評分達 75 分以上的強勢多頭標的。</p>"}

  <h2>📊 全部港股通成分股量化總表（按綜合評分與 RS 強弱排列）</h2>
  <input type="text" id="searchInput" class="search-box" onkeyup="filterTable()" placeholder="輸入股票代碼快速搜尋（例如：0700、9880、9660）...">
  <table id="stockTable">
    <thead>
      <tr>
        <th>代碼</th>
        <th>收盤價 (HKD)</th>
        <th>漲跌幅</th>
        <th>RS 評級 (20日超額)</th>
        <th>MA5 / MA20 / MA60</th>
        <th>RSI (14)</th>
        <th>量比</th>
        <th>綜合評分</th>
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
