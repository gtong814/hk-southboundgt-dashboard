import os
import re
import time
import requests
import akshare as ak
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# 1. 多源獲取完整港股通成分股名單
def get_all_southbound_tickers():
    tickers = set()

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

# 2. Stan Weinstein Stage 1-4 週線階段判斷函數（基於 30 週均線與斜率）
def classify_weinstein_stage(df_daily):
    weekly_close = df_daily["Close"].resample("W-FRI").last().dropna()
    # 改用「每週日均成交量」，避免週一至週四因交易日不足導致量比失真
    weekly_vol_mean = df_daily["Volume"].resample("W-FRI").mean().dropna()

    win = 30 if len(weekly_close) >= 34 else max(15, len(weekly_close) - 4)
    if len(weekly_close) < 19:
        return "N/A", "數據不足", 0.0, 0.0, "badge-neutral"

    wma30 = weekly_close.rolling(win).mean()
    curr_w_close = float(weekly_close.iloc[-1])
    prev_w_close = float(weekly_close.iloc[-2])
    curr_wma = float(wma30.iloc[-1])
    prev_wma_4w = float(wma30.iloc[-5])

    if curr_wma <= 0 or prev_wma_4w <= 0:
        return "N/A", "數據不足", 0.0, 0.0, "badge-neutral"

    wma_slope_pct = ((curr_wma - prev_wma_4w) / prev_wma_4w) * 100
    dist_wma_pct = ((curr_w_close - curr_wma) / curr_wma) * 100

    curr_w_vol = float(weekly_vol_mean.iloc[-1])
    avg_w_vol = float(weekly_vol_mean.iloc[-5:-1].mean()) if len(weekly_vol_mean) >= 5 else curr_w_vol
    w_vol_ratio = curr_w_vol / avg_w_vol if avg_w_vol > 0 else 1.0

    # 取得日線 20 天均線，過濾仍在回調中的弱勢股
    ma20_val = float(df_daily["Close"].rolling(20).mean().iloc[-1])

    # Stage 2：上升推進期
    if curr_w_close > curr_wma and wma_slope_pct > 0.3:
        is_reclaim = prev_w_close <= float(wma30.iloc[-2])
        # 真正的 Stage 2A：必須站上 20 天線、必須放量（>= 1.3x），且剛站回 30 週線或距離不遠
        if curr_w_close > ma20_val and w_vol_ratio >= 1.3 and (is_reclaim or dist_wma_pct <= 8.0):
            return "Stage 2A", "Stage 2A（放量突破上升期）", curr_wma, wma_slope_pct, "badge-bull"
        return "Stage 2", "Stage 2（主升推進期）", curr_wma, wma_slope_pct, "badge-bull"

    # Stage 4：下跌衰落期
    if curr_w_close < curr_wma and wma_slope_pct < -0.3:
        return "Stage 4", "Stage 4（空頭下跌期）", curr_wma, wma_slope_pct, "badge-bear"

    # Stage 1 vs Stage 3
    if abs(wma_slope_pct) <= 0.3 or (curr_w_close > curr_wma and wma_slope_pct <= 0.3) or (curr_w_close < curr_wma and wma_slope_pct >= -0.3):
        lookback = min(26, len(weekly_close) - 1)
        past_price = float(weekly_close.iloc[-lookback])
        half_year_ret = ((curr_w_close - past_price) / past_price) * 100 if past_price > 0 else 0.0

        if half_year_ret > 15.0:
            return "Stage 3", "Stage 3（高檔頭部派發期）", curr_wma, wma_slope_pct, "badge-warn"
        else:
            return "Stage 1", "Stage 1（底部橫行築底期）", curr_wma, wma_slope_pct, "badge-neutral"

    return "Stage 1", "Stage 1（築底觀察期）", curr_wma, wma_slope_pct, "badge-neutral"

# 新增：產出格式化 Excel 報表函數
def export_to_excel(results_data, output_path):
    rows = []
    for r in results_data:
        rows.append({
            "代碼": r["ticker"],
            "置頂": "是" if r["is_pinned"] else "",
            "收盤價": round(r["last_close"], 2),
            "漲跌幅(%)": round(r["pct_change"], 2),
            "Weinstein階段": r["stage_code"],
            "階段說明": r["stage_label"],
            "30週均線": round(r["wma30"], 2),
            "30週線4週斜率(%)": round(r["wma_slope"], 2),
            "RS評級": r["rs_rating"],
            "20日超額報酬(%)": round(r["rs_diff_20d"], 2),
            "60日超額報酬(%)": round(r["rs_diff_60d"], 2),
            "MA5": round(r["ma5"], 2),
            "MA20": round(r["ma20"], 2),
            "MA60": round(r["ma60"], 2),
            "RSI(14)": round(r["rsi14"], 1),
            "量比": round(r["vol_ratio"], 2),
            "20日阻力位": round(r["high_20d"], 2),
            "20日支撐位": round(r["low_20d"], 2),
            "綜合評分": r["score"],
            "技術診斷": r["signals"],
        })

    df_out = pd.DataFrame(rows)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="港股通量化掃描")
        ws = writer.sheets["港股通量化掃描"]

        # 凍結首列 & 開啟自動篩選
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        # 表頭樣式
        header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # 自動調整欄寬（限制上限避免診斷欄位過寬）
        for col_idx, col_cells in enumerate(ws.columns, start=1):
            max_len = 0
            for cell in col_cells:
                val = str(cell.value or "")
                # 中文字元約佔 2 個寬度
                display_len = sum(2 if ord(ch) > 127 else 1 for ch in val)
                if display_len > max_len:
                    max_len = display_len
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = min(max_len + 4, 55)

# 3. 下載大市基準 (2800.HK 盈富基金)
bench_ret_20d = 0.0
bench_ret_60d = 0.0
try:
    bench_df = yf.download("2800.HK", period="1y", interval="1d", progress=False, timeout=15)
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
print(f"共載入 {len(all_tickers)} 隻港股通股份，開始 1 年期日線/週線掃描...")

# 4. 分批下載 1 年日線數據
results = []
batch_size = 100

for i in range(0, len(all_tickers), batch_size):
    batch = all_tickers[i:i + batch_size]
    try:
        data = yf.download(
            batch,
            period="1y",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True,
            timeout=20
        )
    except Exception:
        continue

    if data is None or data.empty:
        continue

    for ticker in batch:
        try:
            df = data[ticker] if len(batch) > 1 else data
            df = df.dropna(subset=["Close"])
            if df.empty or len(df) < 30:
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

            stage_code, stage_label, wma30_val, wma_slope, stage_badge = classify_weinstein_stage(df)

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
                "stage_code": stage_code,
                "stage_label": stage_label,
                "stage_badge": stage_badge,
                "wma30": wma30_val,
                "wma_slope": wma_slope,
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

# 5. 計算全市場 RS Rating 與整合 Weinstein Stage 評分
if results:
    rs_series = pd.Series([r["rs_weighted_excess"] for r in results])
    rs_ranks = (rs_series.rank(pct=True) * 98 + 1).round().astype(int).tolist()
else:
    rs_ranks = []

for item, rs_rating in zip(results, rs_ranks):
    item["rs_rating"] = rs_rating
    score = 50
    signals = []

    if item["stage_code"] == "Stage 2A":
        score += 22
        signals.append(f"處於 {item['stage_label']}，剛放量站上向上傾斜的 30 週線（{item['wma30']:.2f}）。")
    elif item["stage_code"] == "Stage 2":
        score += 18
        signals.append(f"處於 {item['stage_label']}，股價穩守 30 週線（{item['wma30']:.2f}，4週斜率 {item['wma_slope']:+.2f}%）之上。")
    elif item["stage_code"] == "Stage 1":
        score += 2
        signals.append(f"處於 {item['stage_label']}，30 週線（{item['wma30']:.2f}）趨平整理，等待放量突破轉入 Stage 2。")
    elif item["stage_code"] == "Stage 3":
        score -= 8
        signals.append(f"處於 {item['stage_label']}，30 週線（{item['wma30']:.2f}）動能放緩，留意高檔派發風險。")
    elif item["stage_code"] == "Stage 4":
        score -= 20
        signals.append(f"處於 {item['stage_label']}，受壓於向下傾斜的 30 週線（{item['wma30']:.2f}，4週斜率 {item['wma_slope']:+.2f}%）之下。")

    if item["last_close"] > item["ma5"] > item["ma20"] > item["ma60"]:
        score += 12
        signals.append("日線呈現標準多頭排列。")
    elif item["last_close"] < item["ma20"] and item["last_close"] < item["ma60"]:
        score -= 10
        signals.append("日線受壓於 20 天及 60 天線之下。")

    if rs_rating >= 85:
        score += 12
        signals.append(f"相對強弱極強（RS Rating {rs_rating}，近20日跑贏大市 {item['rs_diff_20d']:+.1f}%）。")
    elif rs_rating >= 70:
        score += 6
        signals.append(f"相對強弱跑贏大市（RS Rating {rs_rating}）。")
    elif rs_rating <= 25:
        score -= 8
        signals.append(f"相對大市明顯偏弱（RS Rating {rs_rating}）。")

    if item["vol_ratio"] >= 1.5 and item["pct_change"] > 0:
        score += 10
        signals.append(f"日線放量上漲（量比 {item['vol_ratio']:.2f}x）。")
    elif item["vol_ratio"] >= 1.5 and item["pct_change"] < 0:
        score -= 10
        signals.append(f"日線放量下跌（量比 {item['vol_ratio']:.2f}x）。")

    if item["rsi14"] >= 75:
        score -= 4
        signals.append(f"RSI(14) 達 {item['rsi14']:.1f}（超買區）。")
    elif item["rsi14"] <= 30:
        score += 4
        signals.append(f"RSI(14) 跌至 {item['rsi14']:.1f}（超賣區）。")

    item["score"] = max(0, min(100, score))
    item["signals"] = " ".join(signals)

# 6. 排序、統計與輸出檔案
stage2_count = sum(1 for r in results if r["stage_code"] in ("Stage 2", "Stage 2A"))
stage1_count = sum(1 for r in results if r["stage_code"] == "Stage 1")
stage3_count = sum(1 for r in results if r["stage_code"] == "Stage 3")
stage4_count = sum(1 for r in results if r["stage_code"] == "Stage 4")

results.sort(key=lambda x: (x["is_pinned"], x["score"], x["rs_rating"]), reverse=True)

os.makedirs("public", exist_ok=True)
hkt = timezone(timedelta(hours=8))
now_dt = datetime.now(hkt)
now_hkt = now_dt.strftime("%Y-%m-%d %H:%M:%S HKT")
today_str = now_dt.strftime("%Y%m%d")

# 產出完整 Excel 報表
excel_filename = "southbound_report.xlsx"
export_to_excel(results, os.path.join("public", excel_filename))
print(f"已產出 Excel 報表：public/{excel_filename}")

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
      <td><span class="badge {item['stage_badge']}">{item['stage_code']}</span> <span style="font-size:0.82em;color:#94a3b8;">(30W:{item['wma30']:.2f})</span></td>
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
            <h3>{pin_tag}{item['ticker']} ｜ {item['stage_label']}</h3>
            <div>
              <span class="badge {item['stage_badge']}" style="margin-right:6px;">{item['stage_code']}</span>
              <span class="badge {rs_badge}" style="margin-right:6px;">RS：{item['rs_rating']}</span>
              <span class="badge {badge_class}">綜合評分：{item['score']} / 100</span>
            </div>
          </div>
          <ul>
            <li><strong>Weinstein 階段與技術診斷：</strong>{item['signals']}</li>
            <li><strong>週線與相對強弱：</strong>30週均線 <code>{item['wma30']:.2f}</code>（4週斜率 <code>{item['wma_slope']:+.2f}%</code>）｜ 近20日超額報酬 <code class="{rs_diff_class}">{rs_sign}{item['rs_diff_20d']:.2f}%</code></li>
            <li><strong>日線關鍵點位：</strong>20日阻力位 <code>{item['high_20d']:.2f}</code> ｜ 20日支撐位 <code>{item['low_20d']:.2f}</code> ｜ 月線(MA20) <code>{item['ma20']:.2f}</code></li>
          </ul>
        </div>
        """)

html_output = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>全市場港股通量化決策儀表盤 (Weinstein Stage 1-4 + RS)</title>
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif; background: #0b1120; color: #e2e8f0; max-width: 1240px; margin: 0 auto; padding: 24px; line-height: 1.6; }}
    h1 {{ color: #38bdf8; margin-bottom: 4px; }}
    .meta {{ color: #94a3b8; font-size: 0.9em; margin-bottom: 16px; }}
    .stage-bar {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 24px; background: #1e293b; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; font-size: 0.92em; }}
    .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }}
    .search-box {{ flex: 1; min-width: 240px; padding: 10px 14px; border-radius: 8px; border: 1px solid #334155; background: #1e293b; color: #f8fafc; font-size: 1em; box-sizing: border-box; }}
    .btn {{ padding: 10px 16px; border-radius: 8px; font-size: 0.92em; font-weight: 600; cursor: pointer; text-decoration: none; border: none; display: inline-flex; align-items: center; gap: 6px; transition: opacity 0.15s ease; white-space: nowrap; }}
    .btn:hover {{ opacity: 0.88; }}
    .btn-excel {{ background: #16a34a; color: #ffffff; }}
    .btn-filter-excel {{ background: #0284c7; color: #ffffff; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; background: #1e293b; border-radius: 8px; overflow: hidden; font-size: 0.92em; }}
    th, td {{ padding: 10px 10px; text-align: left; border-bottom: 1px solid #334155; }}
    th {{ background: #0f172a; color: #38bdf8; font-weight: 600; position: sticky; top: 0; }}
    .up {{ color: #22c55e; font-weight: bold; }}
    .down {{ color: #ef4444; font-weight: bold; }}
    .flat {{ color: #94a3b8; }}
    .card {{ background: #1e293b; border-left: 4px solid #38bdf8; padding: 16px 20px; border-radius: 8px; margin-bottom: 16px; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }}
    .card h3 {{ margin: 0; color: #f8fafc; }}
    .badge {{ padding: 3px 9px; border-radius: 12px; font-size: 0.83em; font-weight: bold; display: inline-block; }}
    .badge-bull {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid #22c55e; }}
    .badge-bear {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }}
    .badge-warn {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }}
    .badge-neutral {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid #64748b; }}
    code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #38bdf8; }}
    ul {{ margin: 0; padding-left: 20px; }}
    li {{ margin-bottom: 6px; }}
  </style>
</head>
<body>
  <h1>🇭🇰 全市場港股通量化掃描儀表盤</h1>
  <div class="meta">最後更新：{now_hkt} ｜ 已掃描港股通標的數：{len(results)} 隻 ｜ 基準 (2800.HK) 20日/60日表現：{bench_ret_20d:+.2f}% / {bench_ret_60d:+.2f}% ｜ 配色：綠升紅跌</div>

  <div class="stage-bar">
    <span><strong>📊 全市場 Stan Weinstein 階段分佈：</strong></span>
    <span class="badge badge-bull">Stage 2 主升期：{stage2_count} 隻</span>
    <span class="badge badge-neutral">Stage 1 築底期：{stage1_count} 隻</span>
    <span class="badge badge-warn">Stage 3 派發期：{stage3_count} 隻</span>
    <span class="badge badge-bear">Stage 4 下跌期：{stage4_count} 隻</span>
    <a href="{excel_filename}" download="港股通量化掃描_{today_str}.xlsx" class="btn btn-excel" style="margin-left:auto;">📥 下載完整 Excel (.xlsx)</a>
  </div>

  <h2>🔥 強勢 Stage 2 及重點置頂股診斷（綜合評分 ≥ 75 分）</h2>
  {"".join(detail_cards) if detail_cards else "<p>今日暫無綜合評分達 75 分以上的強勢標的。</p>"}

  <h2>📋 全部港股通成分股量化總表（支援搜尋代碼或 Stage 階段）</h2>
  <div class="toolbar">
    <input type="text" id="searchInput" class="search-box" onkeyup="filterTable()" placeholder="輸入股票代碼或階段篩選（例如：0700、Stage 2、Stage 2A、Stage 1）...">
    <button type="button" class="btn btn-filter-excel" onclick="exportFilteredTable()">🔍 匯出目前篩選結果 (.xlsx)</button>
  </div>
  <table id="stockTable">
    <thead>
      <tr>
        <th>代碼</th>
        <th>收盤價</th>
        <th>漲跌幅</th>
        <th>Weinstein 階段 (30週線)</th>
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
        const rowText = rows[i].textContent || rows[i].innerText;
        rows[i].style.display = rowText.toUpperCase().indexOf(filter) > -1 ? "" : "none";
      }}
    }}

    function exportFilteredTable() {{
      if (typeof XLSX === "undefined") {{
        alert("Excel 匯出套件載入失敗，請檢查網路連線或使用上方「下載完整 Excel」按鈕。");
        return;
      }}
      const table = document.getElementById("stockTable");
      const rows = table.querySelectorAll("tr");
      const exportData = [];

      rows.forEach((row, idx) => {{
        if (idx === 0 || row.style.display !== "none") {{
          const cells = Array.from(row.querySelectorAll("th, td")).map(c => c.innerText.trim());
          exportData.push(cells);
        }}
      }});

      const ws = XLSX.utils.aoa_to_sheet(exportData);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "篩選結果");

      const keyword = document.getElementById("searchInput").value.trim();
      const suffix = keyword ? "_" + keyword.replace(/[^a-zA-Z0-9\u4e00-\u9fa5_-]/g, "") : "";
      XLSX.writeFile(wb, "港股通篩選_{today_str}" + suffix + ".xlsx");
    }}
  </script>
</body>
</html>
"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html_output)
