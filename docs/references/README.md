# Taipower references

The bundled 電價表 (`src/taipower_tou/data/詳細電價表.md`, from
`docs/詳細電價表.pdf`) leaves some billing rules to other Taipower documents.
The files here fill those gaps. Tests cite them, and none ship with the package.
All were read from Wayback Machine snapshots of Taipower pages.

Taipower has two rule books. The 營業規章 is approved by the 經濟部. The
營業規章施行細則 is Taipower's own detail rules under it. Each has a 第四章
電費之計收, with different articles under the same numbers. The other
chapters kept here set no bill amount. `tests/data/clauses/` says why for each
article.

| File | What it settles | Source | sha256 |
| --- | --- | --- | --- |
| `營業規章第四章_電費之計收_1110907.pdf` | The 營業規章 chapter as amended 111/9/7, the latest. 第二十六、二十七條 count days by 30ths. 第三十九、四十條 take 3‰ of the basic fee off per outage or 卸載 hour. Taipower lists a file of the same size (378.2 KB) on its current page, and the 115/2/5 amendment changed only 第51、78條. | https://web.archive.org/web/20240325193352id_/https://www.taipower.com.tw/upload/158/2022113016271085140.pdf | `494ee4ff83bfeaa75645bb8f2e8bff27e70804a7d848477dbfe27def46dfe506` |
| `營業規章第四章.txt` | The text of the PDF above, extracted with `pdfplumber`, for tests to cite by line. | | `80f04c7d8f8fbf0c5d73d1c17e0ca230b52548a6f389a8fce2cc9efda928589a` |
| `營業規章第六章_供電方式及工程_1110907.pdf` | The 營業規章 chapter as amended 111/9/7. 第四十六條 sets the supply voltage by 契約容量, with 低壓 below 100 kW. No article sets a bill amount. The 115/2/5 amendment added a second paragraph to 第51條, on the 保護電驛 the customer keeps. This file predates it, and page 5 of the notice below has the new text. Taipower listed this file (398.3 KB) until 2025-11 and a 227.8 KB 第六章 by 2026-04. | https://web.archive.org/web/20240718150855id_/https://www.taipower.com.tw/upload/158/2022113016271549811.pdf | `fc0e5718ccbbb5d5b20af1d8ff9d63c5c330c5df120764b0f9fec9c3ee2dbd6e` |
| `營業規章第六章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `fdde8e00dd546f96d5c9df64e7124488ec3d5e18ad5e5c278ad651840562fea9` |
| `營業規章附表_工本費單價表_1110907.pdf` | The 營業規章 附表 as amended 111/9/7. It prices a re-inspection of equipment at 580 to 950 元 a customer, VAT included. No bill amount depends on it. Taipower's page listed a file of the same size (357.9 KB) in 2026-04. | https://web.archive.org/web/20240722023934id_/https://www.taipower.com.tw/upload/158/2022113016273431386.pdf | `2b8712e3f5045d11db7b18233aecaa4a77d07dd6d513b7ae1c5290df1d190676` |
| `營業規章附表.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `bfdd2036237af94163e76a793164cef39de815d5861c257987f467a75f804c16` |
| `營業規章施行細則第四章_電費之計收.pdf` | The 施行細則 chapter, 108/9/17. 第二十八條 最高需量 drops its fraction of a kW. 第二十九條 cuts bill items to the 角 and rounds totals to the 元. 第三十條 adjusts the 超約 fee for 功率因數 below 80%. 第三十八條 counts an unused month at 80%. | https://web.archive.org/web/20251201150430id_/https://www.taipower.com.tw/media/bnlf4e4j/%E7%AC%AC%E5%9B%9B%E7%AB%A0%20%E9%9B%BB%E8%B2%BB%E4%B9%8B%E8%A8%88%E6%94%B6.pdf?mediaDL=true | `bd9e0fb3b849070c3eebb01eb22e15979ad12cd3b6ae254963dc41c452e9ea9c` |
| `營業規章施行細則第四章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `1a8946880d91e8ada4aceca5775fc1d1a5fdf583946361eb68e0a208df1e6d6d` |
| `營業規章施行細則第一章_總則.pdf` | Its 修正沿革 ends at 108/9/17, so the 第四章 above is current. Taipower's page listed a file of the same size in 2026-05. | https://web.archive.org/web/20240519011809id_/https://www.taipower.com.tw/upload/159/2020060114421925270.pdf | `701569c671e914f7f0442a07f6fb6f7d5093c006059906af4b615728fd5fb958` |
| `營業規章施行細則第一章.txt` | The text of the PDF above, extracted with `pdfplumber`. Its 第一條 to 第四條 set no bill amount. | | `3bed7afaee93ff0aa86b79b116218c660fd0cf1e4a6b18a609789c7ea3df0d14` |
| `營業規章施行細則第二章_申請用電.pdf` | The 施行細則 chapter on applying for supply. 第十五條 counts appliances toward a 裝置契約, and 第十九條 splits a 公共設施 meter's bill among the households. Neither changes an amount `calculate_bill` computes, and no other article sets one. Taipower's page listed a file of the same size (208.7 KB) in 2026-05. | https://web.archive.org/web/20251201085137id_/https://www.taipower.com.tw/media/l2xjnsrt/%E7%AC%AC%E4%BA%8C%E7%AB%A0%20%E7%94%B3%E8%AB%8B%E7%94%A8%E9%9B%BB.pdf?mediaDL=true | `fa3b189fc466f7d2ab4fe4e00c1d0c8b3de9c9e939bb879dad29c92f488a7e17` |
| `營業規章施行細則第二章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `7cc5abf9b402bb4cbbf94e341a0d2e8548bd699df44f20670c3ab02a7fc13235` |
| `營業規章施行細則第三章_契約變更及終止.pdf` | The 施行細則 chapter on 過戶, 復電 and 停電. No article sets a bill amount. Taipower's page listed a file of the same size (100.3 KB) in 2026-05. | https://web.archive.org/web/20251209204338id_/https://www.taipower.com.tw/media/ikobggde/%E7%AC%AC%E4%B8%89%E7%AB%A0%20%E5%A5%91%E7%B4%84%E8%AE%8A%E6%9B%B4%E5%8F%8A%E7%B5%82%E6%AD%A2.pdf?mediaDL=true | `67c6f3028a08b7c871c036d43436eb8bd94cd3fec229372bed0ab627489e0c6a` |
| `營業規章施行細則第三章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `25cfe14ed0fb7f81b874e65ab5eef1e6e8dc3834febbc7c6b65dde02da4209c9` |
| `可直接領獎電費帳單樣式.pdf` | Two sample 表燈 bills. Their 流動電費 is cut to the 角 once, after adding every tier and season, and the total is rounded to the 元. | https://web.archive.org/web/20260502034448id_/https://www.taipower.com.tw/media/cgpjt3kc/%E5%8F%AF%E7%9B%B4%E6%8E%A5%E9%A0%98%E7%8D%8E%E9%9B%BB%E8%B2%BB%E5%B8%B3%E5%96%AE%E6%A8%A3%E5%BC%8F.pdf?mediaDL=true | `e71a1381a591d1c53f4c5b88714a584e4988bed79b1c10f83dcb79492f4d54c0` |
| `各類電價表及計算範例_1130401.pdf` | The 高壓 電動車充換電設施電價 table on page 16 has the 6/1–9/30 夏月 and 95% of every 低壓 price, 基本電費 included. Its worked bills use the 113/4/1 prices. | https://web.archive.org/web/20251115050107id_/https://www.taipower.com.tw/media/mpbjpjgj/%E5%90%84%E9%A1%9E%E9%9B%BB%E5%83%B9%E8%A1%A8%E5%8F%8A%E8%A8%88%E7%AE%97%E7%AF%84%E4%BE%8B_1130401.pdf?mediaDL=true | `4002772d1a45cc7a2f62c4a788822ae6afa5b7fc18d98edf9067db270aa8e6c2` |
| `電動車充換電設施電價介紹.pdf` | Taipower's slides on the EV tariff at the 114/10 prices. Page 12 gives 高壓 EV 5% off the whole bill. | https://web.archive.org/web/20251206022145/https://www.taipower.com.tw/media/gqzhlwqx/%E9%9B%BB%E5%8B%95%E8%BB%8A%E5%85%85%E6%8F%9B%E9%9B%BB%E8%A8%AD%E6%96%BD%E9%9B%BB%E5%83%B9%E4%BB%8B%E7%B4%B9.pdf | `9b256f71d1e1edcbae595a374a45cf4b88f23fbee445903bc9e47b4ffce21f2e` |

The 115/2/5 amendment of the 營業規章 is in a Taipower notice reposted at
https://www.aim.org.tw/upload/news/file/1772093229.pdf. Page 4 lists it, and
page 5 has the new 第51、78條.

## Open questions

No Taipower document settles these. The package's readings are in the README.

- Which 契約容量 the 10% of 超約 is taken of, for times after 尖峰 or with
  more than one contract. The tariff, both 第四章, the 113/4/1 and 113/10/16
  計算範例, the 高壓用戶服務網 Q&A and Taipower's FAQ give no such example.
- Whether a 三段式 customer with only a 週六半尖峰 or 離峰 contract pays
  按戶計收. Since the 110/6/10 電價表 first had a 低壓 三段式, its sentence
  leaves 按戶 out, while 二段式 has said 按戶及按 since 2014.
- Whether a time-of-use bill cuts 流動電費 to the 角 per time period or once.
  The sample bills above are both 非時間.

## Read but not kept

Older 電價表 show how the rules changed. None has a 高壓 or 特高壓 非時間電價.

| 電價表 | Source | sha256 |
| --- | --- | --- |
| 107/6/26, with 110 prices | https://web.archive.org/web/20220316105229/https://www.taipower.com.tw/upload/238/2021111716354461653.pdf | `69437f9bed4f93d67a4e17a423aa8e527ccc592112cee58ba892ac66ce863362` |
| 110/6/10, first with a 低壓 三段式 | https://web.archive.org/web/20210915191115/https://www.taipower.com.tw/upload/238/2021062313172068082.pdf | |
| 111/8/11, first with the EV tariff | https://web.archive.org/web/20220824043917/https://www.taipower.com.tw/upload/238/2022081817205673404.pdf | `74849cf235a1f92f5dc110c2027cfd36fc1611f853ec73353bddb41d42d3e8c3` |
| 111/11/9, 高壓 夏月 moves to 5/16–10/15 | https://web.archive.org/web/20221215095208/https://www.taipower.com.tw/upload/238/2022111810252060626.pdf | `0062a4ae702ed45f9f1cfa70416d353f997f6a66ac08be59a625645bd880dc53` |
| 112/11/17 | https://web.archive.org/web/20240222074319/https://www.taipower.com.tw/upload/238/2023112015305580918.pdf | `408cbb8c03d33b70dcee5d10bdea4c573a4b814622df3ac4e786d18bf328c607` |

Other sources:

- Taipower's sustainability page says 高壓 users have all been on 時間電價
  since 1989:
  https://web.archive.org/web/20251119103600/https://service.taipower.com.tw/csr/esg/services/smart-electricity-service
- Taipower's FAQ 請問電費如何計算 prices a tiered bill that spans two seasons:
  https://web.archive.org/web/20260313135517/https://www.taipower.com.tw/2289/2363/2388/2389/10735/normalPost
- Secondary worked 超約 bills: WIS bills each time's excess at its own
  contract price,
  https://www.wis-tw.com/post/%E5%A5%91%E7%B4%84%E5%AE%B9%E9%87%8F%E8%88%87%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9 ,
  and POXA's 離峰 example fits every reading of the 10% but the 離峰
  contract alone, https://poxa.io/report/20260413 .

No public list of the days of 三段式尖峰時間可變動時間電價 was found. Taipower
notifies each customer the day before.
