# Taipower references

The bundled 電價表 (`src/taipower_tou/data/詳細電價表.md`, from
`docs/詳細電價表.pdf`) leaves some billing rules to other Taipower documents.
The files here fill those gaps. Tests cite them, and none ship with the package.
Taipower's files were read from Wayback Machine snapshots of its pages,
except the 營業規章's 第一至三章 and 第五至十章 and the 114/10/1 計算範例. The
maintainer downloaded those from Taipower on 2026-10-28, the chapters from its
營業規章 page, https://www.taipower.com.tw/2289/2484/51434/51760/?mid=158 .

Taipower has two rule books. The 營業規章 is approved by the 經濟部. The
營業規章施行細則 is Taipower's own detail rules under it. Each has a 第四章
電費之計收, with different articles under the same numbers. Of the other
chapters kept here, only 營業規章 第三條 and 第十二條 bear on a bill. They
make a 需量 a 15-minute average. `tests/data/clauses/` says why for each
article.

| File | What it settles | Source | sha256 |
| --- | --- | --- | --- |
| `營業規章第一章_總則_1150625.pdf` | The 營業規章 chapter with the book's 修正沿革, which ends at 115/6/25. No amendment after 108/2/18 names an article of 第一章. 第三條第十款 makes a 需量契約容量 a 十五分鐘平均瓩數, and 第十二款 makes the 用電最高需量 the month's highest. | Taipower's 營業規章 page, downloaded 2026-10-28 | `8e269512a381a030b37fc8a3b20db68d1cc9df769d52d5d35cce70646c02a625` |
| `營業規章第一章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `fad3aa22ddd7be74cb2a8f7e293f39aca3b0a352519619f6d785387ca96b2b17` |
| `營業規章第二章_申請用電_1110907.pdf` | The chapter as amended 111/9/7, which changed 第五條. 第十二條 makes a 需量契約容量 the agreed highest 15-minute demand. No other article sets a bill amount. | Taipower's 營業規章 page, downloaded 2026-10-28 | `74591e7937a91a83450eba8e342a16ee3b9e8afdc9ec354a944f5ad53ea70017` |
| `營業規章第二章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `db8591dbb1fe5cc5c7a840717753db6911d16d6d83d36eace090d28d7851ec3f` |
| `營業規章第三章_契約變更及終止_1110907.pdf` | The chapter as amended 108/10/17 (第十五條) and 111/9/7 (第二十一條), on 過戶, 暫停用電 and 停止供電. No article sets a bill amount. | Taipower's 營業規章 page, downloaded 2026-10-28 | `ee8e8eab43d760f28a1e138dcc984b3ffddd96d5ada61a44279fde05327d6419` |
| `營業規章第三章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `babe1b0ad60a860e37360bb55a8ef514a44fd4635d5db4ebde4081413096d1f1` |
| `營業規章第四章_電費之計收_1110907.pdf` | The 營業規章 chapter as amended 111/9/7, the latest. 第二十六、二十七條 count days by 30ths. 第三十九、四十條 take 3‰ of the basic fee off per outage or 卸載 hour. The file on Taipower's 營業規章 page on 2026-10-28 is the same, byte for byte. | https://web.archive.org/web/20240325193352id_/https://www.taipower.com.tw/upload/158/2022113016271085140.pdf | `494ee4ff83bfeaa75645bb8f2e8bff27e70804a7d848477dbfe27def46dfe506` |
| `營業規章第四章.txt` | The text of the PDF above, extracted with `pdfplumber`, for tests to cite by line. | | `80f04c7d8f8fbf0c5d73d1c17e0ca230b52548a6f389a8fce2cc9efda928589a` |
| `營業規章第五章_違規用電_1080218.pdf` | The chapter as revised 108/2/18, not amended since. 違規用電 owes 追償電費 at 臨時電價, apart from a bill. | Taipower's 營業規章 page, downloaded 2026-10-28 | `9cb3368beb075803f8b6c22e642a35f23cec4f311d09a99b00ab898428504cab` |
| `營業規章第五章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `07cc35400835ceffce75db6588b5412904e33e0a6d2d1b9dbd2d847a03540f60` |
| `營業規章第六章_供電方式及工程_1150625.pdf` | The chapter as amended 115/6/25. 第四十六條 sets the supply voltage by 契約容量, with 低壓 below 100 kW. Since 115/6/25 one company's branches in one building or neighbouring plants add up their 契約容量 to choose 69, 161 or 345 kV. 115/2/5 added the second paragraph of 第五十一條, on 保護電驛. No article sets a bill amount. | Taipower's 營業規章 page, downloaded 2026-10-28 | `d8d2606a794aaee9e26f019d7b2900ef9abbfaf3c3911f06c201862f896039cd` |
| `營業規章第六章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `645b1a252f5a0040df3a15a1e4357f054c3957bc9a0c2c34977430b707eca141` |
| `營業規章第七章_線路設置費_1150205.pdf` | The chapter as amended 115/2/5, which changed 第七十八條. 線路設置費 and 復電費 are paid when applying for supply or restoring it, not in the bill. | Taipower's 營業規章 page, downloaded 2026-10-28 | `9da265aed4bd7a4a9613848ee5a5bc77f081281a46cfcbc7176d419e97cee78c` |
| `營業規章第七章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `f898582dbb63be43c4bf9174e68adf2b1fca8dd71395bc460eea76724fac53bf` |
| `營業規章第八章_供電線路遷移工料費_1080218.pdf` | The chapter as revised 108/2/18, not amended since, on 遷移工料費. No article sets a bill amount. | Taipower's 營業規章 page, downloaded 2026-10-28 | `0d2af6981a75646ef66a88b777edf943b528bd8fb1c9397a266bb24562a0b4b2` |
| `營業規章第八章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `df48c373cb9182eedad9697ac5f20efc4cbbee0f8bec88f1a0d0005fb185d5a3` |
| `營業規章第九章_用電設備租用_1110907.pdf` | The chapter as amended 111/9/7, which changed 第一百零四條. Rent for Taipower's equipment is not an electricity charge. | Taipower's 營業規章 page, downloaded 2026-10-28 | `0e87c7424912e1266577d219150e08be08b54d9c05c32079eef6605b8bf22cf0` |
| `營業規章第九章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `6ab756a6b782ae450382acb7a1c50f110e856fc11831ca1c4aa1de6fd52ef252` |
| `營業規章第十章_附則_1080218.pdf` | The chapter as revised 108/2/18, not amended since. | Taipower's 營業規章 page, downloaded 2026-10-28 | `5a47e8e3ec54245302b4d315fe83b638057c6f3bb16167a0480d87d62f049cc1` |
| `營業規章第十章.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `d4bd3d4b0f7f5c1615ae6dbea1f2f3daab654d1b9a479ddd1f375cbc0a14d439` |
| `營業規章附表_工本費單價表_1110907.pdf` | The 營業規章 附表 as amended 111/9/7. It prices a re-inspection of equipment at 580 to 950 元 a customer, VAT included. No bill amount depends on it. The file on Taipower's 營業規章 page on 2026-10-28 is the same, byte for byte. | https://web.archive.org/web/20240722023934id_/https://www.taipower.com.tw/upload/158/2022113016273431386.pdf | `2b8712e3f5045d11db7b18233aecaa4a77d07dd6d513b7ae1c5290df1d190676` |
| `營業規章附表.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `bfdd2036237af94163e76a793164cef39de815d5861c257987f467a75f804c16` |
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
| `各類電價表及計算範例_1141001.pdf` | The 114/10/1 edition, with the bundled 電價表's prices. Each of its 24 worked bills is for one 8月. The 15 with a 需量契約 all assume 倘最高需量未超過契約容量, and no 單價×度數 product has a 分 digit, so none settles an Open question below. Page 16 takes 95% of a 高壓 電動車 bill after rounding the bill to the 元, 89,729元×95%=85,243元. `tests/test_worked_examples.py` bills each example. | https://www.taipower.com.tw/media/wzicn04w/%E5%90%84%E9%A1%9E%E9%9B%BB%E5%83%B9%E8%A1%A8%E5%8F%8A%E8%A8%88%E7%AE%97%E7%AF%84%E4%BE%8B.pdf?mediaDL=true , downloaded 2026-10-28 | `7cc52610922cc3e85a54585f5c6f15ace093a069f2cc93e32257cac8dca4ba6c` |
| `各類電價表及計算範例_1141001.txt` | The text of the PDF above, extracted with `pdfplumber`. | | `daba5ee6142f3d8aa4cfb16d57fb54cc55087a995ad5eb55bd357da76e69d90a` |
| `電動車充換電設施電價介紹.pdf` | Taipower's slides on the EV tariff at the 114/10 prices. Page 12 gives 高壓 EV 5% off the whole bill. | https://web.archive.org/web/20251206022145/https://www.taipower.com.tw/media/gqzhlwqx/%E9%9B%BB%E5%8B%95%E8%BB%8A%E5%85%85%E6%8F%9B%E9%9B%BB%E8%A8%AD%E6%96%BD%E9%9B%BB%E5%83%B9%E4%BB%8B%E7%B4%B9.pdf | `9b256f71d1e1edcbae595a374a45cf4b88f23fbee445903bc9e47b4ffce21f2e` |

第一章's 修正沿革 lists every amendment of the 營業規章. Since the 108/2/18
revision, 108/10/17 amended 第15條, 111/9/7 第5、21、28、29、30、32、39、46、
54、57、65、66、72、79、83、84、104條 and the 附表, 115/2/5 第51、78條, and
115/6/25 第46條.

## Open questions

No Taipower document settles these. The package's readings are in the README.

- Which 契約容量 the 10% of 超約 is taken of, for times after 尖峰 or with
  more than one contract. The tariff, both 第四章, the 113/4/1, 113/10/16 and
  114/10/1 計算範例, the 高壓用戶服務網 Q&A and Taipower's FAQ give no such
  example.
- Whether a 三段式 customer with only a 週六半尖峰 or 離峰 contract pays
  按戶計收. Since the 110/6/10 電價表 first had a 低壓 三段式, its sentence
  leaves 按戶 out, while 二段式 has said 按戶及按 since 2014. The 114/10/1
  計算範例's 低壓 三段式 bill has a 經常契約.
- Whether a time-of-use bill cuts 流動電費 to the 角 per time period or once.
  The sample bills above are both 非時間. In the 114/10/1 計算範例 every
  單價×度數 product ends in 0 分, so both ways give its totals.

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
