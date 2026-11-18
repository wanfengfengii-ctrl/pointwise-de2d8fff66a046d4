# 水厂转运日批数仓

出水班和池区分别提供各端点的整升日报。值班员提供当日名册和物理开放路线。封存员用两套汇总计数核定日批，班长用收据核对来源，质控员用成果号补查路线组。两侧总量相等时，开放路线仍可能无法承接全部计数。

## 运行

在仓库根目录使用 Python 3.11。只依赖标准库及其中的 SQLite。

```sh
python3 -B -S verify.py
python3 -B -S demo.py
python3 -B -S -m unittest discover -s tests -t . -v
```

`verify.py` 执行完整回归。`demo.py` 读取 `samples/daily.json` 与 `samples/expected.json`，在独立临时库中核对旧成果和同日后续成果，并输出实际收据和界限与手算预期的对照。打开普通业务库只初始化表结构。重开及重复初始化保留原修订和成果。

## 一天的工作流程

1. 用 `RouteCatalog(path)` 打开路线账，通过 `put_routes(catalog, day, revision, lines, pools, open_routes)` 整体登记双侧名册和开放路线，取回固定路线回执。
2. 用 `CounterLedger(path)` 打开计数账。从具名日报导入时，先对两侧分别调用 `collect_counter_entries(rows)`，在生成映射前发现重复记录。通过 `stage_counters(ledger, day, revision, lines, pools)` 登记两侧计数映射，取回固定计数回执。
3. 同日同号同内容可重试，输入顺序不影响内容比较。补报或工况更正以新修订号登记。两账的 `get(day, revision)` 返回该版修订，缺失时返回 `None`。
4. 用 `ArchiveStore(path)` 打开成果库。调用 `certify(ledger, catalog, archive, day, counter_revision, route_revision)`，指定两份同日来源。仓内按侧核对完整名册，再验证所有逐端计数可沿所选路线同时满足。
5. 通过接纳时，同一事务保存固定证据和收据，提交后返回正整数成果号。可用 `before_commit` 关键字提供接收临时成果号的同步回调，测试提交前失败。回调异常原样传播，本次成果和收据均回滚。
6. 用 `read_receipt(archive, artifact_id)` 核对业务日、两项修订和两侧总升数。`get_sealed_batch(archive, artifact_id)` 可读回固定证据。
7. 用 `bounds(archive, artifact_id, routes)` 查询后来选定的一组线池对，取得 `[最小值, 最大值]`。四条路线均开放且 A、B、X、Y 各报 1 升时，A 到 X 为 `[0, 1]`，所有入 X 路线合计为 `[1, 1]`，A 到 X 与 B 到 Y 合计为 `[0, 2]`。
8. 通过各库的 `close()` 释放连接。关闭源账后，只重开成果库也可凭旧号读收据与补查。较新的同日成果有自己的成果号。

## Python 入口与输入

| 模块 | 入口 |
| --- | --- |
| `counters.imports` | `stage_counters`、`collect_counter_entries` |
| `counters.ledger` | `CounterLedger` |
| `routes.registration` | `put_routes` |
| `routes.catalog` | `RouteCatalog` |
| `settlement.admission` | `certify` |
| `archive.store` | `ArchiveStore` |
| `archive.lookup` | `read_receipt`、`get_sealed_batch` |
| `accounts.bounds` | `bounds` |

业务日、修订号和端点名是非空文本，样例使用 ISO 日期作为日期键。端点身份有侧别。名册和路线组按集合处理，路线为有序的线池对。两侧计数接受非负的 Python 内置整数。布尔、文本、浮点、空值和负数均属非法输入。显式零是有效记录，封存时也须覆盖。数据库载荷使用十六进制整数文本保存精确升数，可表示超过 SQLite 有符号整数范围的计数。

路线组上下界分别在全部合法整数分配上计算。未选开放路线仍可承接计数。已知端点之间的关闭路线贡献为零。空组、纯关闭组和全零批的合法查询返回 `[0, 0]`，重复开放路线只计一次。任一未知端点使整组请求失败。多次核账彼此独立，输入顺序或 SQLite 行顺序不影响业务结果。

## 失败边界

计数或路线登记失败使用 `CounterInputError`、`RouteInputError`、`CounterRevisionConflict` 或 `RouteRevisionConflict`。`SourceBindingError` 表示所选来源缺失、身份不符或名册覆盖不完整。`InfeasibleBatchError` 表示计数无法同时成立。接纳拒绝发生在归档写入前。存储或提交异常沿原异常传播。

未知成果号产生 `UnknownArtifactError`。已知成果上的错误查询产生 `QueryInputError` 或其子类 `UnknownEndpointError`。成果与收据缺项、载荷无法解析或两者不匹配时产生 `ArchiveConsistencyError`。成果和收据按同一成果号读取，旧号始终引用其原封存版本。
