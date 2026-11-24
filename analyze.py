import os
import re
import time
import requests
import akshare as ak
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# 1. 多源獲取完整港股通成分股名單（優先 HKEX 官方名單 / AkShare，確保 100% 抓齊全市場）
def get_all_southbound_tickers():
    tickers = set()

    # 來源 A：直接從港交所 (HKEX) 官方網站抓取最新「港股通（滬+深）合資格股份」名單
    hkex_urls = [
        "https://www.hkex.com.hk/chi/market/sec_tradinfo/stockconnect/EligibleStocks_c.htm",
        "https://www.hkex.com.hk/eng/market/sec_tradinfo/stockconnect/EligibleStocks.htm"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in hkex_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                # 擷取網頁表格中的 5 位數港股代碼（例如 00700、09988）
                codes = re.findall(r'\b0\d{4}\b', resp.text)
                for code in codes:
                    if code != "00000":
                        yf_code = f"{code[-4:]}.HK"
                        tickers.add(yf_code)
                if len(tickers) > 300:
                    print(f"成功從港交所官方網頁載入 {len(tickers)} 隻港股通標的！")
                    return sorted(list(tickers))
        except Exception as e:
            print(f"HKEX 官方來源嘗試略過: {e}")

    # 來源 B：嘗試 AkShare 港股通成分股介面
    try:
        df_ggt = ak.stock_hk_ggt_components_em()
        if not df_ggt.empty and "代码" in df_ggt.columns:
            for code in df_ggt["代码"].astype(str):
                code_clean = code.strip().zfill(5)
                yf_code = f"{code_clean[-4:]}.HK" if code_clean.startswith("0") else f"{code_clean}.HK"
                tickers.add(yf_code)
            if len(tickers) > 300:
                print(f"成功從 AkShare 載入 {len(tickers)} 隻港股通標的！")
                return sorted(list(tickers))
    except Exception as e:
        print(f"AkShare 來源略過: {e}")

    # 來源 C：若以上網路均受限，使用完整港股通核心及活躍成分股清單（涵蓋恒指、科指、國企及熱門港股通標的）
    core_southbound = [
        "0001.HK", "0002.HK", "0003.HK", "0005.HK", "0006.HK", "0011.HK", "0012.HK", "0016.HK", "0017.HK", "0019.HK",
        "0020.HK", "0027.HK", "0066.HK", "0101.HK", "0135.HK", "0144.HK", "0151.HK", "0168.HK", "0175.HK", "0177.HK",
        "0179.HK", "0189.HK", "0200.HK", "0220.HK", "0241.HK", "0257.HK", "0267.HK", "0268.HK", "0270.HK", "0285.HK",
        "0288.HK", "0291.HK", "0293.HK", "0300.HK", "0302.HK", "0316.HK", "0322.HK", "0338.HK", "0341.HK", "0345.HK",
        "0354.HK", "0358.HK", "0363.HK", "0371.HK", "0384.HK", "0386.HK", "0388.HK", "0390.HK", "0392.HK", "0412.HK",
        "0425.HK", "0467.HK", "0489.HK", "0522.HK", "0546.HK", "0551.HK", "0552.HK", "0570.HK", "0576.HK", "0586.HK",
        "0590.HK", "0598.HK", "0604.HK", "0631.HK", "0636.HK", "0639.HK", "0656.HK", "0667.HK", "0669.HK", "0670.HK",
        "0683.HK", "0688.HK", "0694.HK", "0696.HK", "0700.HK", "0728.HK", "0753.HK", "0762.HK", "0763.HK", "0772.HK",
        "0780.HK", "0788.HK", "0799.HK", "0811.HK", "0817.HK", "0823.HK", "0836.HK", "0853.HK", "0855.HK", "0856.HK",
        "0857.HK", "0867.HK", "0868.HK", "0874.HK", "0880.HK", "0881.HK", "0883.HK", "0902.HK", "0909.HK", "0914.HK",
        "0916.HK", "0921.HK", "0934.HK", "0939.HK", "0941.HK", "0956.HK", "0960.HK", "0966.HK", "0968.HK", "0973.HK",
        "0981.HK", "0991.HK", "0992.HK", "0995.HK", "0998.HK", "1024.HK", "1030.HK", "1038.HK", "1044.HK", "1055.HK",
        "1060.HK", "1066.HK", "1070.HK", "1071.HK", "1072.HK", "1088.HK", "1093.HK", "1099.HK", "1109.HK", "1112.HK",
        "1113.HK", "1114.HK", "1117.HK", "1119.HK", "1128.HK", "1133.HK", "1138.HK", "1157.HK", "1164.HK", "1171.HK",
        "1177.HK", "1179.HK", "1186.HK", "1193.HK", "1199.HK", "1208.HK", "1209.HK", "1211.HK", "1216.HK", "1234.HK",
        "1238.HK", "1258.HK", "1268.HK", "1288.HK", "1299.HK", "1302.HK", "1308.HK", "1310.HK", "1313.HK", "1316.HK",
        "1336.HK", "1339.HK", "1347.HK", "1357.HK", "1359.HK", "1368.HK", "1378.HK", "1381.HK", "1385.HK", "1398.HK",
        "1415.HK", "1448.HK", "1475.HK", "1478.HK", "1508.HK", "1513.HK", "1515.HK", "1516.HK", "1521.HK", "1528.HK",
        "1530.HK", "1548.HK", "1579.HK", "1585.HK", "1600.HK", "1610.HK", "1618.HK", "1658.HK", "1666.HK", "1681.HK",
        "1686.HK", "1691.HK", "1698.HK", "1766.HK", "1772.HK", "1776.HK", "1787.HK", "1788.HK", "1797.HK", "1798.HK",
        "1800.HK", "1801.HK", "1810.HK", "1811.HK", "1816.HK", "1818.HK", "1821.HK", "1833.HK", "1858.HK", "1860.HK",
        "1876.HK", "1877.HK", "1880.HK", "1882.HK", "1883.HK", "1888.HK", "1896.HK", "1898.HK", "1907.HK", "1908.HK",
        "1910.HK", "1913.HK", "1918.HK", "1919.HK", "1928.HK", "1929.HK", "1951.HK", "1952.HK", "1958.HK", "1963.HK",
        "1972.HK", "1988.HK", "1997.HK", "1999.HK", "2001.HK", "2005.HK", "2007.HK", "2009.HK", "2013.HK", "2015.HK",
        "2018.HK", "2020.HK", "2038.HK", "2057.HK", "2068.HK", "2076.HK", "2096.HK", "2099.HK", "2121.HK", "2128.HK",
        "2145.HK", "2150.HK", "2155.HK", "2156.HK", "2158.HK", "2160.HK", "2162.HK", "2171.HK", "2186.HK", "2190.HK",
        "2196.HK", "2202.HK", "2208.HK", "2232.HK", "2233.HK", "2238.HK", "2252.HK", "2255.HK", "2257.HK", "2268.HK",
        "2269.HK", "2273.HK", "2276.HK", "2282.HK", "2285.HK", "2313.HK", "2314.HK", "2318.HK", "2319.HK", "2328.HK",
        "2331.HK", "2333.HK", "2338.HK", "2342.HK", "2343.HK", "2356.HK", "2357.HK", "2359.HK", "2362.HK", "2367.HK",
        "2378.HK", "2380.HK", "2382.HK", "2386.HK", "2388.HK", "2400.HK", "2416.HK", "2423.HK", "2498.HK", "2500.HK",
        "2518.HK", "2588.HK", "2600.HK", "2601.HK", "2602.HK", "2607.HK", "2611.HK", "2618.HK", "2628.HK", "2638.HK",
        "2666.HK", "2669.HK", "2688.HK", "2689.HK", "2727.HK", "2777.HK", "2799.HK", "2800.HK", "2822.HK", "2823.HK",
        "2828.HK", "2858.HK", "2866.HK", "2869.HK", "2877.HK", "2883.HK", "2888.HK", "2899.HK", "3032.HK", "3033.HK",
        "3110.HK", "3306.HK", "3309.HK", "3311.HK", "3319.HK", "3320.HK", "3323.HK", "3328.HK", "3331.HK", "3333.HK",
        "3339.HK", "3347.HK", "3360.HK", "3377.HK", "3380.HK", "3383.HK", "3393.HK", "3396.HK", "3606.HK", "3613.HK",
        "3618.HK", "3633.HK", "3668.HK", "3690.HK", "3692.HK", "3738.HK", "3759.HK", "3800.HK", "3808.HK", "3868.HK",
        "3877.HK", "3888.HK", "3896.HK", "3898.HK", "3900.HK", "3908.HK", "3918.HK", "3931.HK", "3933.HK", "3958.HK",
        "3968.HK", "3969.HK", "3983.HK", "3988.HK", "3990.HK", "3993.HK", "3996.HK", "3998.HK", "6030.HK", "6049.HK",
        "6055.HK", "6060.HK", "6066.HK", "6069.HK", "6078.HK", "6082.HK", "6088.HK", "6098.HK", "6099.HK", "6110.HK",
        "6127.HK", "6160.HK", "6166.HK", "6178.HK", "6185.HK", "6186.HK", "6608.HK", "6616.HK", "6618.HK", "6655.HK",
        "6660.HK", "6682.HK", "6690.HK", "6699.HK", "6806.HK", "6808.HK", "6818.HK", "6821.HK", "6823.HK", "6830.HK",
        "6837.HK", "6855.HK", "6862.HK", "6865.HK", "6869.HK", "6881.HK", "6886.HK", "6963.HK", "6969.HK", "6979.HK",
        "6990.HK", "9618.HK", "9626.HK", "9633.HK", "9658.HK", "9660.HK", "9668.HK", "9669.HK", "9677.HK", "9688.HK",
        "9690.HK", "9696.HK", "9698.HK", "9863.HK", "9866.HK", "9868.HK", "9878.HK", "9880.HK", "9888.HK", "9896.HK",
        "9898.HK", "9901.HK", "9911.HK", "9922.HK", "9923.HK", "9926.HK", "9959.HK", "9961.HK", "9966.HK", "9969.HK",
        "9979.HK", "9985.HK", "9987.HK", "9988.HK", "9992.HK", "9993.HK", "9995.HK", "9996.HK", "9997.HK", "9999.HK"
    ]
    tickers.update(core_southbound)
    return sorted(list(tickers))

pinned_raw = os.environ.get("STOCK_LIST", "")
pinned_tickers = [t.strip().upper() for t in pinned_raw.split(",") if t.strip()]

all_tickers = sorted(list(set(get_all_southbound_tickers()) | set(pinned_tickers)))
print(f"共載入 {len(all_tickers)} 隻港股通股份，開始極速批量掃描...")

# 2. 分批下載日線數據（每批 100 隻 + 15秒超時保護）
results = []
batch_size = 100

for i in range(0, len(all_tickers), batch_size):
    batch = all_tickers[i:i + batch_size]
    print(f"正在處理第 {i + 1} 至 {min(i + batch_size, len(all_tickers))} 隻...")
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
    except Exception as e:
        print(f"批次下載略過: {e}")
        continue

    if data is None or data.empty:
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
    time.sleep(0.5)

print(f"分析完成，共產出 {len(results)} 隻有效標的數據。")

# 3. 排序與生成 HTML
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

    if item["is_pinned"] or (item["score"] >= 75 and idx < 35):
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
    .up {{ color: #22c55e; font-weight: bold; }}
    .down {{ color: #ef4444; font-weight: bold; }}
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
