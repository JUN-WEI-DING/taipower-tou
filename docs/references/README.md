# Taipower references

The bundled 電價表 (`src/taipower_tou/data/詳細電價表.md`, from
`docs/詳細電價表.pdf`) leaves some billing rules to other Taipower documents.
The files here fill those gaps. Tests cite them, and none ship with the package.
All were read from Wayback Machine snapshots of Taipower pages.

| File | What it settles | Source | sha256 |
| --- | --- | --- | --- |
| `營業規章第四章_電費之計收.pdf` | 第二十八條 最高需量 drops its fraction of a kW. 第二十九條 rounds bill items to 角 and totals to 元. 第三十條 adjusts the 超約 fee for 功率因數 below 80%. 第三十八條 counts an unused month at 80%. The PDF was made from `1080917-細則第四章.docx` on 2019-11-18, so later amendments may be missing. | https://web.archive.org/web/20251201150430id_/https://www.taipower.com.tw/media/bnlf4e4j/%E7%AC%AC%E5%9B%9B%E7%AB%A0%20%E9%9B%BB%E8%B2%BB%E4%B9%8B%E8%A8%88%E6%94%B6.pdf?mediaDL=true | `bd9e0fb3b849070c3eebb01eb22e15979ad12cd3b6ae254963dc41c452e9ea9c` |
| `營業規章第四章.txt` | The text of the PDF above, extracted with `pdfplumber`, for tests to cite by line. | | `1a8946880d91e8ada4aceca5775fc1d1a5fdf583946361eb68e0a208df1e6d6d` |
| `各類電價表及計算範例_1130401.pdf` | The 高壓 電動車充換電設施電價 table on page 16 has the 6/1–9/30 夏月 and 95% of every 低壓 price, 基本電費 included. Its worked bills use the 113/4/1 prices. | https://web.archive.org/web/20251115050107id_/https://www.taipower.com.tw/media/mpbjpjgj/%E5%90%84%E9%A1%9E%E9%9B%BB%E5%83%B9%E8%A1%A8%E5%8F%8A%E8%A8%88%E7%AE%97%E7%AF%84%E4%BE%8B_1130401.pdf?mediaDL=true | `4002772d1a45cc7a2f62c4a788822ae6afa5b7fc18d98edf9067db270aa8e6c2` |
| `電動車充換電設施電價介紹.pdf` | Taipower's slides on the EV tariff at the 114/10 prices. Page 12 gives 高壓 EV 5% off the whole bill. | https://web.archive.org/web/20251206022145/https://www.taipower.com.tw/media/gqzhlwqx/%E9%9B%BB%E5%8B%95%E8%BB%8A%E5%85%85%E6%8F%9B%E9%9B%BB%E8%A8%AD%E6%96%BD%E9%9B%BB%E5%83%B9%E4%BB%8B%E7%B4%B9.pdf | `9b256f71d1e1edcbae595a374a45cf4b88f23fbee445903bc9e47b4ffce21f2e` |

## Read but not kept

Older 電價表 show how the rules changed. None has a 高壓 or 特高壓 非時間電價.

| 電價表 | Source | sha256 |
| --- | --- | --- |
| 107/6/26, with 110 prices | https://web.archive.org/web/20220316105229/https://www.taipower.com.tw/upload/238/2021111716354461653.pdf | `69437f9bed4f93d67a4e17a423aa8e527ccc592112cee58ba892ac66ce863362` |
| 111/8/11, first with the EV tariff | https://web.archive.org/web/20220824043917/https://www.taipower.com.tw/upload/238/2022081817205673404.pdf | `74849cf235a1f92f5dc110c2027cfd36fc1611f853ec73353bddb41d42d3e8c3` |
| 111/11/9, 高壓 夏月 moves to 5/16–10/15 | https://web.archive.org/web/20221215095208/https://www.taipower.com.tw/upload/238/2022111810252060626.pdf | `0062a4ae702ed45f9f1cfa70416d353f997f6a66ac08be59a625645bd880dc53` |
| 112/11/17 | https://web.archive.org/web/20240222074319/https://www.taipower.com.tw/upload/238/2023112015305580918.pdf | `408cbb8c03d33b70dcee5d10bdea4c573a4b814622df3ac4e786d18bf328c607` |

Other sources:

- Taipower's sustainability page says 高壓 users have all been on 時間電價
  since 1989:
  https://web.archive.org/web/20251119103600/https://service.taipower.com.tw/csr/esg/services/smart-electricity-service
- Taipower's FAQ 請問電費如何計算 prices a tiered bill that spans two seasons:
  https://web.archive.org/web/20260313135517/https://www.taipower.com.tw/2289/2363/2388/2389/10735/normalPost
- A worked 三段式 超約 bill that bills each time's excess at its own contract
  price (secondary):
  https://www.wis-tw.com/post/%E5%A5%91%E7%B4%84%E5%AE%B9%E9%87%8F%E8%88%87%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9

No public list of the days of 三段式尖峰時間可變動時間電價 was found. Taipower
notifies each customer the day before.
