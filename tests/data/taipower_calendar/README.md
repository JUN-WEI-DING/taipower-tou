# Taipower TOU calendars

`<year>.csv` lists every day of one year with its day type (`sunday_holiday`,
`saturday`, or `weekday`), read from the cell colours of Taipower's official
時間電價日曆表 PDF. Tests use these files as ground truth for off-peak days.

To regenerate a year, install `pdfplumber` and run:

```
python scripts/read_tou_calendar_pdf.py <calendar.pdf> --out tests/data/taipower_calendar
```

Each PDF page holds one year. Where a year appears in more than one PDF, every
copy gives the same CSV. The PDFs below are the ones the CSVs were written from.
Older files come from Wayback Machine snapshots of Taipower pages.

| Years | Calendar (printed date) | Source | sha256 |
| --- | --- | --- | --- |
| 2014, 2015 | 103年 (102/8/30製), 104年 (103/9/1製) | https://web.archive.org/web/20150514141028/http://www.taipower.com.tw/UpFile/_userfiles/file/103~104%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf | `c2dfc97574d32fca1a016b21ef5ea969cb7ec9b7cfb6964e0fc1b67544570d1b` |
| 2016 | 105年 (104/9/3製) | https://web.archive.org/web/20160705025838/http://www.taipower.com.tw:80/UpFile/_userfiles/file/104~105%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf | `7d9ff078757727a946cf115ff029e043faafc9f3a4d980b5ee6a97f0af1086b1` |
| 2017 | 106年 (105/9/21製) | https://web.archive.org/web/20170518210322/http://www.taipower.com.tw:80/UpFile/_userfiles/file/105~106%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf | `4ddadb7df328af8e5a33a054c8a7b7ad9b488c02c114414f39d506cf7e628ce9` |
| 2018 | 107年 (106/9/5製) | https://web.archive.org/web/20170908172811/http://www.taipower.com.tw:80/UpFile/_userfiles/file/106~107%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf | `9a04ea4200f5c42e5fa33df254475d3173a3113709f32e83aba822be24e17184` |
| 2019 | 108年 (107/8/23製) | https://web.archive.org/web/20191015095911/http://branch.taipower.com.tw/WebTools/FilesDownload.ashx?Siteid=564766277367364243&MmmID=616151233622046352&fd=NewsLetter_Flies&RD=1&Pname=%E9%99%84%E4%BB%B6108%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf | `85a11eb8c389ccffd904d1d48a35055d4fcc5249281b295713393cc8a2b019a0` |
| 2020, 2021 | 109年 (108/8/30製), 110年 (109/8/12製) | https://web.archive.org/web/20210306022621/https://www.taipower.com.tw/upload/238/2020082410573334884.pdf | `8e9812b2ff9b15a72dfcd5cb34b88affe1b8c59be86a113886db2dc6fcf1e826` |
| 2022 | 111年 (110/9/9製) | https://web.archive.org/web/20211204035731/https://www.taipower.com.tw/upload/238/2021091414353711829.pdf | `53297cc0741a750498b8edbb00596f694c832509b9077bdf02bd75e7b52da1e3` |
| 2023 | 112年 (111/8/8製) | https://web.archive.org/web/20220824044048/https://www.taipower.com.tw/upload/238/2022080914131443766.pdf | `75f54da96cd77110426dcae5bd31ac3588b5b5ef2020a8b73ecf27da5d8ad1a5` |
| 2024 | 113年 (112/6/1製) | https://web.archive.org/web/20240222062033/https://www.taipower.com.tw/upload/238/2023060510125076474.pdf | `c4a5da59b42b65bcdedf6515c1c8f696fdd7d90d122f445cc8ae7a4ad1f2c4ab` |
| 2025 | 114年 (114/8/26修) | https://web.archive.org/web/20260331160859/https://www.taipower.com.tw/media/5c5d3mrv/%E5%8F%B0%E9%9B%BB114%E5%8F%8A115%E5%B9%B4%E6%99%82%E9%96%93%E9%9B%BB%E5%83%B9%E6%97%A5%E6%9B%86%E8%A1%A8.pdf?mediaDL=true | `37b0a513ca06ed5920647a199ad4170cca74b54b5cbf15540c72bd35f35c9258` |
| 2026, 2027 | 115年 (114/8/26製), 116年 (115/7/2製) | 最近兩年時間電價日曆表.pdf, linked from https://www.taipower.com.tw/2289/2290/46940/46945/normalPost | `649e8d877925af801aaa1997d07db485c8ed7856544ac6618479835cd8100bf5` |

2025 uses the revised calendar. The original 114年 calendar (113/7/8製) lacks
2025-10-25 and 2025-12-25, which the 114/9/1 電價表 revision added.

The 116年 calendar is also at
https://service.taipower.com.tw/branch/files/file_pool/1/0Q195347998596417147/台電116年時間電價日曆表.pdf
(sha256 `3bfd5d4a0cca85ded10b2e98fea7089785be3cb32ceec2ee2ef97436fc9f14fd`) and
gives the same `2027.csv`.
