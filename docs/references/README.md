# Taipower references

The bundled 電價表 (`src/taipower_tou/data/詳細電價表.md`, from
`docs/詳細電價表.pdf`) leaves some billing rules to other Taipower documents.
The files here fill those gaps. Tests cite them, and none ship with the package.
Taipower's files were read from Wayback Machine snapshots of its pages,
except `營業規章全文_1080218_台電函.pdf`, a Taipower letter reposted by the
中華民國電機技師公會. The texts in `secondary/` are not Taipower's. See
Secondary transcriptions below.

Taipower has two rule books. The 營業規章 is approved by the 經濟部. The
營業規章施行細則 is Taipower's own detail rules under it. Each has a 第四章
電費之計收, with different articles under the same numbers. Of the other
chapters kept here, only 營業規章 第三條 and 第十二條 bear on a bill. They
make a 需量 a 15-minute average. `tests/data/clauses/` says why for each
article.

| File | What it settles | Source | sha256 |
| --- | --- | --- | --- |
| `營業規章第四章_電費之計收_1110907.pdf` | The 營業規章 chapter as amended 111/9/7, the latest. 第二十六、二十七條 count days by 30ths. 第三十九、四十條 take 3‰ of the basic fee off per outage or 卸載 hour. Taipower lists a file of the same size (378.2 KB) on its current page, and the 115/2/5 amendment changed only 第51、78條. | https://web.archive.org/web/20240325193352id_/https://www.taipower.com.tw/upload/158/2022113016271085140.pdf | `494ee4ff83bfeaa75645bb8f2e8bff27e70804a7d848477dbfe27def46dfe506` |
| `營業規章第四章.txt` | The text of the PDF above, extracted with `pdfplumber`, for tests to cite by line. | | `80f04c7d8f8fbf0c5d73d1c17e0ca230b52548a6f389a8fce2cc9efda928589a` |
| `營業規章第六章_供電方式及工程_1110907.pdf` | The 營業規章 chapter as amended 111/9/7. 第四十六條 sets the supply voltage by 契約容量, with 低壓 below 100 kW. No article sets a bill amount. The 115/2/5 amendment added a second paragraph to 第51條, on the 保護電驛 the customer keeps. This file predates it, and page 5 of the notice below has the new text. Taipower listed this file (398.3 KB) until 2025-12-11 and a 227.8 KB 第六章 (`/media/slmh1n33/`) from 2026-03-13. The Wayback Machine has no copy of the newer file. | https://web.archive.org/web/20240718150855id_/https://www.taipower.com.tw/upload/158/2022113016271549811.pdf | `fc0e5718ccbbb5d5b20af1d8ff9d63c5c330c5df120764b0f9fec9c3ee2dbd6e` |
| `營業規章第六章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `fdde8e00dd546f96d5c9df64e7124488ec3d5e18ad5e5c278ad651840562fea9` |
| `營業規章附表_工本費單價表_1110907.pdf` | The 營業規章 附表 as amended 111/9/7. It prices a re-inspection of equipment at 580 to 950 元 a customer, VAT included. No bill amount depends on it. Taipower's page listed a file of the same size (357.9 KB) in 2026-04. | https://web.archive.org/web/20240722023934id_/https://www.taipower.com.tw/upload/158/2022113016273431386.pdf | `2b8712e3f5045d11db7b18233aecaa4a77d07dd6d513b7ae1c5290df1d190676` |
| `營業規章附表.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `bfdd2036237af94163e76a793164cef39de815d5861c257987f467a75f804c16` |
| `營業規章全文_1080218_台電函.pdf` | Taipower's letter 電配售部業字第10800032292號 of 108/2/26, with the whole 營業規章 as revised 108/2/18 attached. Since then 108/10/17 amended 第15條, 111/9/7 第5、21、28、29、30、32、39、46、54、57、65、66、72、79、83、84、104條 and the 附表, and 115/2/5 第51、78條 (the 修正沿革 on page 4 of the 115/2/5 notice below). No article of 第一、五、八、十章 is among them, so for those chapters this is the current text. Against the 111/9/7 第四、六章 above, it differs only in the amended articles, in spacing, and in 第二十六條's item numbers, which the newer file corrects from 三、四 to 一、二. The Wayback Machine has none of Taipower's own files for these chapters. | https://www.elecpe.org.tw/wp-content/uploads/groupdownload/OfficalDocument/2-36.pdf | `f8b7797d1dc0b96cb1f4617bfca202a5728c9c8566c78c9f02c1a3302e39449e` |
| `營業規章第一章.txt` | 第一章 of the PDF above (pages 9 and 10), cut from its `pdfplumber` text. 第三條第十款 makes a 需量契約容量 a 十五分鐘平均瓩數, and 第十二款 makes the 用電最高需量 the month's highest. | | `715185e019fb32daf6e47e1b1286a258514af26edeb2c5f4b66a563e6cca0103` |
| `營業規章第五章.txt` | 第五章 of the PDF above (pages 22 and 23). 違規用電 owes 追償電費 at 臨時電價, apart from a bill. | | `07cc35400835ceffce75db6588b5412904e33e0a6d2d1b9dbd2d847a03540f60` |
| `營業規章第八章.txt` | 第八章 of the PDF above (pages 38 to 40), on 遷移工料費. No article sets a bill amount. | | `df48c373cb9182eedad9697ac5f20efc4cbbee0f8bec88f1a0d0005fb185d5a3` |
| `營業規章第十章.txt` | 第十章 of the PDF above (page 41). | | `d4bd3d4b0f7f5c1615ae6dbea1f2f3daab654d1b9a479ddd1f375cbc0a14d439` |
| `營業規章施行細則第四章_電費之計收.pdf` | The 施行細則 chapter, 108/9/17. 第二十八條 最高需量 drops its fraction of a kW. 第二十九條 cuts bill items to the 角 and rounds totals to the 元. 第三十條 adjusts the 超約 fee for 功率因數 below 80%. 第三十八條 counts an unused month at 80%. | https://web.archive.org/web/20251201150430id_/https://www.taipower.com.tw/media/bnlf4e4j/%E7%AC%AC%E5%9B%9B%E7%AB%A0%20%E9%9B%BB%E8%B2%BB%E4%B9%8B%E8%A8%88%E6%94%B6.pdf?mediaDL=true | `bd9e0fb3b849070c3eebb01eb22e15979ad12cd3b6ae254963dc41c452e9ea9c` |
| `營業規章施行細則第四章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `1a8946880d91e8ada4aceca5775fc1d1a5fdf583946361eb68e0a208df1e6d6d` |
| `營業規章施行細則第一章_總則.pdf` | Its 修正沿革 ends at 108/9/17, so the 第四章 above is current. Taipower's page listed a file of the same size in 2026-05. | https://web.archive.org/web/20240519011809id_/https://www.taipower.com.tw/upload/159/2020060114421925270.pdf | `701569c671e914f7f0442a07f6fb6f7d5093c006059906af4b615728fd5fb958` |
| `營業規章施行細則第一章.txt` | The text of the PDF above, extracted with `pdfplumber`. Its 第一條 to 第四條 set no bill amount. | | `3bed7afaee93ff0aa86b79b116218c660fd0cf1e4a6b18a609789c7ea3df0d14` |
| `營業規章施行細則第二章_申請用電.pdf` | The 施行細則 chapter on applying for supply. 第十五條 counts appliances toward a 裝置契約, and 第十九條 splits a 公共設施 meter's bill among the households. Neither changes an amount `calculate_bill` computes, and no other article sets one. Taipower's page listed a file of the same size (208.7 KB) in 2026-05. | https://web.archive.org/web/20251201085137id_/https://www.taipower.com.tw/media/l2xjnsrt/%E7%AC%AC%E4%BA%8C%E7%AB%A0%20%E7%94%B3%E8%AB%8B%E7%94%A8%E9%9B%BB.pdf?mediaDL=true | `fa3b189fc466f7d2ab4fe4e00c1d0c8b3de9c9e939bb879dad29c92f488a7e17` |
| `營業規章施行細則第二章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `7cc5abf9b402bb4cbbf94e341a0d2e8548bd699df44f20670c3ab02a7fc13235` |
| `營業規章施行細則第三章_契約變更及終止.pdf` | The 施行細則 chapter on 過戶, 復電 and 停電. No article sets a bill amount. Taipower's page listed a file of the same size (100.3 KB) in 2026-05. | https://web.archive.org/web/20251209204338id_/https://www.taipower.com.tw/media/ikobggde/%E7%AC%AC%E4%B8%89%E7%AB%A0%20%E5%A5%91%E7%B4%84%E8%AE%8A%E6%9B%B4%E5%8F%8A%E7%B5%82%E6%AD%A2.pdf?mediaDL=true | `67c6f3028a08b7c871c036d43436eb8bd94cd3fec229372bed0ab627489e0c6a` |
| `營業規章施行細則第三章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `25cfe14ed0fb7f81b874e65ab5eef1e6e8dc3834febbc7c6b65dde02da4209c9` |
| `營業規章施行細則第五章_違規用電.pdf` | The 施行細則 chapter on 違規用電. 第七十三至八十條 work 追償電費 from appliance capacity and assumed hours, apart from a bill. Taipower's page listed a file of the same size (191.2 KB) in 2026-05. | https://web.archive.org/web/20251130235657id_/https://www.taipower.com.tw/media/f5zbuwrw/%E7%AC%AC%E4%BA%94%E7%AB%A0%20%E9%81%95%E8%A6%8F%E7%94%A8%E9%9B%BB.pdf?mediaDL=true | `aff8d64a2e8794eff9cb7d27ba0ac653b30ae1fc4cd3f9053d68099af28ae821` |
| `營業規章施行細則第五章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `c5ecbb2f927d29666f4f23c7ae230e0694202484da3eb91153c35cab93b42853` |
| `營業規章施行細則第六章_供電方式及工程.pdf` | The 施行細則 chapter on supply and meters. 第八十一條 bills a customer kept on 高壓 supply below the 高壓 minimum at 低壓需量 prices, which is a choice of plan id. 第九十條 re-bills after a failed meter test. Taipower's page listed a file of the same size (270.8 KB) in 2026-05. | https://web.archive.org/web/20251217234444id_/https://www.taipower.com.tw/media/2zqapkpr/%E7%AC%AC%E5%85%AD%E7%AB%A0%20%E4%BE%9B%E9%9B%BB%E6%96%B9%E5%BC%8F%E5%8F%8A%E5%B7%A5%E7%A8%8B.pdf?mediaDL=true | `e881c895da8c99a23eb45b9a9973bb959affbc080110f5d166768310067108b3` |
| `營業規章施行細則第六章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `fe2a14c69d854256b518a9872ac5885725d195902968ce57efbae4fb18669e65` |
| `營業規章施行細則第七章_線路設置費.pdf` | The 施行細則 chapter on 線路設置費 and 復電費, paid when applying, not in the bill. Taipower's page listed a file of the same size (329.7 KB) in 2026-05. | https://web.archive.org/web/20251208152641id_/https://www.taipower.com.tw/media/e55jrule/%E7%AC%AC%E4%B8%83%E7%AB%A0%20%E7%B7%9A%E8%B7%AF%E8%A8%AD%E7%BD%AE%E8%B2%BB.pdf?mediaDL=true | `4eda0d71f2bb37af4250617b96c5b1338c9f180126043f14ba01a2cf49fac8b7` |
| `營業規章施行細則第七章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `7d0bbf300fbb5aaebb0fcd055ee2fe8aa218c4aa79f915f58d61781f6f39b59c` |
| `營業規章施行細則第八章_供電線路遷移工料費.pdf` | The 施行細則 chapter on 遷移工料費. No article sets a bill amount. Taipower's page listed a file of the same size (116.7 KB) in 2026-05. | https://web.archive.org/web/20251130142811id_/https://www.taipower.com.tw/media/pwknziif/%E7%AC%AC%E5%85%AB%E7%AB%A0%20%E4%BE%9B%E9%9B%BB%E7%B7%9A%E8%B7%AF%E9%81%B7%E7%A7%BB%E5%B7%A5%E6%96%99%E8%B2%BB.pdf?mediaDL=true | `823b1b0d9cdff715497f35dcc51b1445135ba2c54980096324e153961d9edf01` |
| `營業規章施行細則第八章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `050803b4c635f7996c15d479eb7ac2c46764cc932f972667a4c4f7aac2ee5441` |
| `營業規章施行細則第九章_設備之租用與賠償.pdf` | The 施行細則 chapter on rented equipment and damages. 第一百卅四條 collects a monthly rent with the bill, but the rent is not an electricity charge. Taipower's page listed a file of the same size (103.1 KB) in 2026-05. | https://web.archive.org/web/20251130231915id_/https://www.taipower.com.tw/media/z04l5dk5/%E7%AC%AC%E4%B9%9D%E7%AB%A0%20%E8%A8%AD%E5%82%99%E4%B9%8B%E7%A7%9F%E7%94%A8%E8%88%87%E8%B3%A0%E5%84%9F.pdf?mediaDL=true | `3ca792067172b128f2bf7ed79ee670340d9bdf8fe45a31389bca64478b10e808` |
| `營業規章施行細則第九章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `22e0fd9da58417806b8542356aa11aace61c9b8ecca8cd342463d5f4b9d653ae` |
| `營業規章施行細則第十章_附則.pdf` | The 施行細則's last article, 第一百卅八條. Taipower's page listed a file of the same size (18.9 KB) in 2026-05. | https://web.archive.org/web/20251130085929id_/https://www.taipower.com.tw/media/tuhjdjtr/%E7%AC%AC%E5%8D%81%E7%AB%A0%20%E9%99%84%E5%89%87.pdf?mediaDL=true | `979d12cd5d49a64ddf5106b8281b9222158ba15d6b441b77b8ef17f529de93d3` |
| `營業規章施行細則第十章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `f97f48fcbd4eb274b923e343edea9ecbf5de432d9b928ffc216c7154ff34bbea` |
| `營業規章施行細則附表_電度表零件及賠償單價.pdf` | The 施行細則 附表一 and 附表二, what a customer pays to repair or replace a meter (第八十九條). No bill amount depends on them. Taipower's page listed a file of the same size (219.4 KB) in 2026-05. | https://web.archive.org/web/20260129194901id_/https://www.taipower.com.tw/media/rcbf2o0w/%E9%99%84%E8%A1%A8.pdf?mediaDL=true | `47b3cf044f98e565a8e1a0a58408809b280514713b7276a9a0ff270b38840526` |
| `營業規章施行細則附表.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `95feff477bd09ff41a029c464e744f362d7857bff5de3090703048bcf0d073b5` |
| `可直接領獎電費帳單樣式.pdf` | Two sample 表燈 bills. Their 流動電費 is cut to the 角 once, after adding every tier and season, and the total is rounded to the 元. | https://web.archive.org/web/20260502034448id_/https://www.taipower.com.tw/media/cgpjt3kc/%E5%8F%AF%E7%9B%B4%E6%8E%A5%E9%A0%98%E7%8D%8E%E9%9B%BB%E8%B2%BB%E5%B8%B3%E5%96%AE%E6%A8%A3%E5%BC%8F.pdf?mediaDL=true | `e71a1381a591d1c53f4c5b88714a584e4988bed79b1c10f83dcb79492f4d54c0` |
| `各類電價表及計算範例_1130401.pdf` | The 高壓 電動車充換電設施電價 table on page 16 has the 6/1–9/30 夏月 and 95% of every 低壓 price, 基本電費 included. Its worked bills use the 113/4/1 prices. | https://web.archive.org/web/20251115050107id_/https://www.taipower.com.tw/media/mpbjpjgj/%E5%90%84%E9%A1%9E%E9%9B%BB%E5%83%B9%E8%A1%A8%E5%8F%8A%E8%A8%88%E7%AE%97%E7%AF%84%E4%BE%8B_1130401.pdf?mediaDL=true | `4002772d1a45cc7a2f62c4a788822ae6afa5b7fc18d98edf9067db270aa8e6c2` |
| `電動車充換電設施電價介紹.pdf` | Taipower's slides on the EV tariff at the 114/10 prices. Page 12 gives 高壓 EV 5% off the whole bill. | https://web.archive.org/web/20251206022145/https://www.taipower.com.tw/media/gqzhlwqx/%E9%9B%BB%E5%8B%95%E8%BB%8A%E5%85%85%E6%8F%9B%E9%9B%BB%E8%A8%AD%E6%96%BD%E9%9B%BB%E5%83%B9%E4%BB%8B%E7%B4%B9.pdf | `9b256f71d1e1edcbae595a374a45cf4b88f23fbee445903bc9e47b4ffce21f2e` |

The 115/2/5 amendment of the 營業規章 is in a Taipower notice reposted at
https://www.aim.org.tw/upload/news/file/1772093229.pdf. Page 4 lists it, and
page 5 has the new 第51、78條.

## Secondary transcriptions

The Wayback Machine has none of Taipower's files for 營業規章 第二、三、七、九章,
and each has an article amended after 108/2/18. The files in `secondary/` are
those chapters from 植根法律網's 111/9/7 transcription, a third party's copy, so
`tests/data/clauses/` can list their articles. Each is the page's text cut at
the chapter headings, with indents removed and a space put after each article
number. Do not cite them as Taipower's words.

Of the 87 articles no amendment has touched since 108/2/18, 植根法律網 reads the
same as Taipower's 108/2/18 text but for five. It has the newer item numbers in
第二十六條, ％ for ‰ in 第四十條, a half-width X in 第五十條, the 附表 inside
第五十九條, and no tables in 第四十條 or 第六十七條. It predates the 115/2/5
第七十八條.

Source: https://www.rootlaw.com.tw/LawArticle.aspx?LawID=A040100050007900-1110907

| File | Articles | sha256 |
| --- | --- | --- |
| `secondary/營業規章第二章_植根法律網_1110907.txt` | 第四至十三條. 111/9/7 amended 第五條. | `49fdfc71aad5ec9465d9d2c222380c7c29383b55873e301042c69a069d9997f3` |
| `secondary/營業規章第三章_植根法律網_1110907.txt` | 第十四至二十一條. 108/10/17 amended 第十五條, and 111/9/7 第二十一條. | `8bedc1f2b5332ba02d9dc31fdfa983599629e4c8baa55fabdc872b3635dbf5c2` |
| `secondary/營業規章第七章_植根法律網_1110907.txt` | 第七十一至八十八條. 111/9/7 amended 第七十二、七十九、八十三、八十四條, and 115/2/5 第七十八條. | `0a9cc6b361ed8e53306616538ff334d6490edd404172fb9956964143c609b032` |
| `secondary/營業規章第九章_植根法律網_1110907.txt` | 第一百零三至一百零五條. 111/9/7 amended 第一百零四條. | `498ff53a1434145af5d098e8eb6c34ab09c6526003244eb163a850f4086736bd` |

## Not found

Taipower's 營業規章 page in its 2026-04-20 snapshot lists these files. None is
in the Wayback Machine, by CDX or by `id_` fetch, with or without
`?mediaDL=true`. Neither are the old site's `upload/158/` files for the same
chapters.

| Chapter | Listed file | Size |
| --- | --- | --- |
| 第一章 總則 | `/media/ijqavc04/` (`/media/s2oncuc5/`, 373.2 KB, until 2025-12) | 199.6 KB |
| 第二章 申請用電 | `/media/frjlhzi5/` | 426.4 KB |
| 第三章 契約變更及終止 | `/media/xr1n2ym1/` | 366.1 KB |
| 第五章 違規用電 | `/media/f5ppdw5a/` | 326 KB |
| 第六章 供電方式及工程 | `/media/slmh1n33/` | 227.8 KB |
| 第七章 線路設置費 | `/media/0ggdrzos/` (`/media/fn0dgpov/`, 375 KB, until 2025-12) | 205.3 KB |
| 第八章 供電線路遷移工料費 | `/media/vikdglwb/` | 332.9 KB |
| 第九章 用電設備租用 | `/media/5tqje0tu/` | 354.6 KB |
| 第十章 附則 | `/media/vxjlnp4u/` | 324 KB |

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
