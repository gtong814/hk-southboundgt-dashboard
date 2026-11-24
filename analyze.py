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
                    print(f"成功從港交所官方網頁載入 {len(tickers)} 隻港股通標的！")
                    return sorted(list(tickers))
        except Exception as e:
            print(f"HKEX 官方來源嘗試略過: {e}")

    # 來源 B：AkShare 港股通成分股介面
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

    # 來源 C：核心港股通成分股保底清單
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
        "2828.HK", "2858.HK", "2866.HK", "2869.HK", "2877.HK", "2883.HK", "2888.HK", "289
