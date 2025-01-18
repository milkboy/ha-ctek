# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/milkboy/ha-ctek/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                      |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------ | -------: | -------: | ------: | --------: |
| custom\_components/ctek/\_\_init\_\_.py   |       90 |       64 |     29% |25-28, 44-143, 157-160, 168-169, 179-217 |
| custom\_components/ctek/api.py            |      146 |      113 |     23% |26-28, 37, 42-47, 52-57, 62, 83-92, 96-138, 149-176, 186-210, 216-245, 249-258, 274, 278-279, 291-336, 342-348, 352, 356, 369-395 |
| custom\_components/ctek/binary\_sensor.py |       23 |       23 |      0% |     3-108 |
| custom\_components/ctek/config\_flow.py   |       89 |       29 |     67% |26-27, 83-91, 192-203, 211, 221-273, 279-304 |
| custom\_components/ctek/const.py          |       14 |        0 |    100% |           |
| custom\_components/ctek/coordinator.py    |      327 |      274 |     16% |26-31, 62-76, 82-88, 92-94, 100-108, 113-118, 122-126, 130-170, 174-182, 186-225, 229-262, 266-298, 310-313, 324-363, 367-389, 393-458, 462-506, 510-516, 520-526, 532-547, 551-552, 561-644, 648-670, 682, 688-693, 697-702, 706-714, 718 |
| custom\_components/ctek/data.py           |       94 |        5 |     95% |     11-17 |
| custom\_components/ctek/entity.py         |       38 |       19 |     50% |15-17, 43-57, 62, 67-73 |
| custom\_components/ctek/enums.py          |       37 |       14 |     62% |39-44, 48, 69-74, 78 |
| custom\_components/ctek/number.py         |       48 |       48 |      0% |     3-139 |
| custom\_components/ctek/sensor.py         |       42 |       42 |      0% |     3-214 |
| custom\_components/ctek/switch.py         |       67 |       67 |      0% |     3-199 |
| custom\_components/ctek/ws.py             |       77 |       57 |     26% |29-39, 43-48, 52-62, 66-116, 120-127, 131 |
|                                 **TOTAL** | **1092** |  **755** | **31%** |           |


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