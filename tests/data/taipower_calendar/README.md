# Taipower TOU calendars

`<year>.csv` lists every day of one year with its day type (`sunday_holiday`,
`saturday`, or `weekday`), read from the cell colours of Taipower's official
時間電價日曆表 PDF. Tests use these files as ground truth for off-peak days.

To regenerate them, install `pdfplumber` and run:

```
python scripts/read_tou_calendar_pdf.py 最近兩年時間電價日曆表.pdf --out tests/data/taipower_calendar
```

| Year | PDF title | Printed date | Source PDF | sha256 |
| --- | --- | --- | --- | --- |
| 2026 | 115年時間電價日曆表 | 114/8/26製 | 最近兩年時間電價日曆表.pdf, page 1 | `649e8d877925af801aaa1997d07db485c8ed7856544ac6618479835cd8100bf5` |
| 2027 | 116年時間電價日曆表 | 115/7/2製 | 最近兩年時間電價日曆表.pdf, page 2 | `649e8d877925af801aaa1997d07db485c8ed7856544ac6618479835cd8100bf5` |
| 2027 | 116年時間電價日曆表 | 115/7/2製 | 台電116年時間電價日曆表.pdf | `3bfd5d4a0cca85ded10b2e98fea7089785be3cb32ceec2ee2ef97436fc9f14fd` |

Both 116年 PDFs produce the same `2027.csv`.

Sources:

- 最近兩年時間電價日曆表.pdf is linked from the listing page
  https://www.taipower.com.tw/2289/2290/46940/46945/normalPost.
- 台電116年時間電價日曆表.pdf is at
  https://service.taipower.com.tw/branch/files/file_pool/1/0Q195347998596417147/台電116年時間電價日曆表.pdf.
