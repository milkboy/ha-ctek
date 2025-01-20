# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/milkboy/ha-ctek/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                      |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------ | -------: | -------: | ------: | --------: |
| custom\_components/ctek/\_\_init\_\_.py   |       90 |       61 |     32% |25-28, 44-143, 158, 168-169, 179-217 |
| custom\_components/ctek/api.py            |      146 |      113 |     23% |26-28, 37, 42-47, 52-57, 62, 83-92, 96-138, 149-176, 186-210, 216-245, 249-258, 274, 278-279, 291-336, 342-348, 352, 356, 369-395 |
| custom\_components/ctek/binary\_sensor.py |       23 |       23 |      0% |     3-108 |
| custom\_components/ctek/config\_flow.py   |       89 |       29 |     67% |26-27, 83-91, 192-203, 211, 221-273, 279-320 |
| custom\_components/ctek/const.py          |       14 |        0 |    100% |           |
| custom\_components/ctek/coordinator.py    |      299 |      244 |     18% |28-34, 67-81, 87-93, 97-99, 105-113, 118-123, 127-132, 136-176, 180-188, 192, 202-235, 239-271, 283-286, 297-336, 340-362, 366-372, 376-382, 388-403, 407-408, 418-524, 533-559, 565-587, 599, 605-610, 614-619, 623-631, 635 |
| custom\_components/ctek/data.py           |       94 |        5 |     95% |     11-17 |
| custom\_components/ctek/entity.py         |       38 |       19 |     50% |15-17, 43-57, 62, 67-73 |
| custom\_components/ctek/enums.py          |       37 |       14 |     62% |39-44, 48, 69-74, 78 |
| custom\_components/ctek/number.py         |       48 |       48 |      0% |     3-139 |
| custom\_components/ctek/parser.py         |       61 |       51 |     16% |17-61, 66-131, 136-178 |
| custom\_components/ctek/sensor.py         |       42 |       42 |      0% |     3-214 |
| custom\_components/ctek/switch.py         |       67 |       67 |      0% |     3-203 |
| custom\_components/ctek/ws.py             |       77 |       57 |     26% |29-39, 43-48, 52-62, 66-116, 120-127, 131 |
|                                 **TOTAL** | **1125** |  **773** | **31%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/milkboy/ha-ctek/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/milkboy/ha-ctek/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/milkboy/ha-ctek/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/milkboy/ha-ctek/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fmilkboy%2Fha-ctek%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/milkboy/ha-ctek/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.