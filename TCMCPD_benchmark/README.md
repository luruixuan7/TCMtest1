# TCMCPD 医案语料：数据分析与基线实验

对公开数据集 **TCMCPD v1.0**（Zenodo `10.5281/zenodo.20929034`，CC BY 4.0）做的**数据分析实验**与
**基线（18 模型）评测实验**，以及两者产出的结果。

本仓库只含三部分：**数据**、**实验脚本**、**结果**。

## 结构

```
TCMCPD_benchmark/                       61 个文件
├── README.md · NOTICE.md · requirements.txt · CHECKSUMS.sha256
│   （另有 .gitattributes / .gitignore）
├── data/        TCMCPD v1.0 原始数据，18 文件（entities + relationships + 说明），未修改
├── scripts/     14 个：数据分析实验 8 + baseline 流水线 5 + 预处理 1
└── results/     18 个 JSON + 5 张图（PNG）
```

规模：**18 数据 + 14 脚本 + 23 结果 + 6 根文件 = 61**。

## 实验与脚本、结果的对应

| 编号 | 实验内容 | 脚本 | 结果文件 |
|---|---|---|---|
| E0 | 数据范围与质量事实（规模、覆盖率、命名、单位、日期） | `scripts/experiments/e0_data_scope.py` | `results/e0_data_scope.json` |
| E1 | 标签存在律（记录完整性 → 是否带证型，AUC 0.933） | `scripts/experiments/e1_e2_patterns.py` | `results/e1_e2_patterns.json` |
| E2 | 可学性定律（频次 vs 结构分解） | 同上 | `results/e1_e2_patterns.json` |
| E3 | 18 个基线模型的指标分歧 | `scripts/pipeline/bench_*.py` + `scripts/experiments/e3_metric_divergence.py` | `results/e3_b1_all_models.json`、`results/e3_b2_all_models.json`、`results/e3_metric_divergence.json` |
| E4 | 划分泄漏（6 个模型族，患者级 vs 就诊级） | `scripts/experiments/e4b_leakage_gradient.py` | `results/appendix/leakage_gradient.json` |
| E5 | 任务可行性（处方持续性、last-basket、增量、间隔） | `scripts/experiments/e5_*.py`、`scripts/experiments/e5b_vocabulary_scope.py` | `results/e5/*.json`、`results/appendix/vocabulary_scope.json` |
| — | 预处理口径与计数 | `scripts/prep/prep_tcmcpd.py` | `results/prep/prep_manifest.json` |

## 运行

```bash
pip install -r requirements.txt

python scripts/prep/prep_tcmcpd.py             # 预处理口径与计数
python scripts/experiments/e0_data_scope.py    # E0
python scripts/experiments/e5_task_feasibility.py
python scripts/experiments/e4b_leakage_gradient.py
```

**基线实验（E3）的流水线，顺序不可颠倒：**

```bash
python scripts/pipeline/bench_data.py B1        # 缓存张量
python scripts/pipeline/bench_models.py B1      # 17 个模型
python scripts/pipeline/bench_extra.py B1       # ModernNCA 式
python scripts/pipeline/bench_tabpfn.py B1      # TabPFN v2（需独立 py3.10 环境）
python scripts/pipeline/bench_eval.py B1        # 统一评测
# B2 同理；之后可跑 e3_metric_divergence.py 与 e1_e2_patterns.py
```

`e1_e2_patterns.py` 依赖 `bench_eval.py` 保存的逐模型预测，必须先跑完 E3 流水线。中间产物 `bench/`
（逐模型预测 `.npz`，体积大）不入库。

## 结果文件 → 产生它的脚本（含交付时改名）

脚本写的路径与交付文件名不完全一致，对照如下；★ 表示该脚本未随本精简包分发（结果文件仍保留归档）：

| 脚本写出 | 交付文件名 |
|---|---|
| `analysis/e0_data_scope.json` | `results/e0_data_scope.json` |
| `analysis/pattern_discovery.json` | `results/e1_e2_patterns.json` |
| `bench/results_B1.json`、`bench/results_B2.json` | `results/e3_b1_all_models.json`、`results/e3_b2_all_models.json` |
| `analysis/e3_metric_divergence.json` | `results/e3_metric_divergence.json` |
| `results/appendix/leakage_gradient.json`、`vocabulary_scope.json` | 同名，直接写入 |
| `bench/results_<task>.json`（B4 绝对下次处方） | `results/e5/e5_b4_absolute.json` |
| `bench/results_B4delta.json` | `results/e5/e5_b4_delta.json` |
| `analysis/results_task_audit.json` | `results/e5/e5_task_feasibility.json` |
| `results/prep/prep_manifest.json` | 同名，直接写入 |
| ★ `bench/equivalence.json` | `results/appendix/equivalence.json` |
| ★ `bench/robustness.json` | `results/appendix/robustness.json` |
| ★ `analysis/revised_analysis.json` | `results/appendix/revised_analysis.json` |
| ★ `results/appendix/r2_increment_test.json` | 同名 |
| ★ `bench/audit_bench.json` | `results/appendix/verification_models.json` |
| ★ `analysis/data_analysis_verification.json` | `results/appendix/verification_data.json` |
| ★ `results/model_prg.json`（PRG 打分器） | 同名 |

## 精简说明

本包为**精简版**，只保留数据、数据分析与 baseline 实验脚本、以及结果。相比完整版额外移出：

| 内容 | 说明 |
|---|---|
| `scripts/appendix/`（6 个） | 稳健性、等效性、分布复核脚本；其产出的 6 个 `results/appendix/*.json` 仍保留 |
| `scripts/models/prg.py` | PRG 打分器；`results/model_prg.json` 仍保留 |
| `scripts/figures/make_figures.py` | 出图脚本；`results/figures/` 的 5 张 PNG 仍保留 |
| `results/figures/*.pdf`（5 个） | 与 PNG 重复的矢量版，只留 PNG |
| `paper/`、`docs/`、`scripts/audit/` | 论文、设计文档、审计脚本，全部在完整版/服务器上 |

因此上表打 ★ 的 7 个 JSON 与 5 张 PNG 在本包内**没有对应产生脚本**，属归档结果；需要重跑这些分析请取完整版。

### 另：`data/.../graph/` 未包含（2 个 CSV，48 MiB）

`graph/neo4j_nodes.csv`（24.5 MiB）与 `graph/neo4j_edges.csv`（23.6 MiB）是数据集作者提供的
**Neo4j 导入用导出**，内容与 `entities/` + `relationships/` 冗余，**本包所有脚本都不读它**。
因其单个文件超过 GitHub 网页上传的 25 MB 上限，故不纳入仓库；需要时从 Zenodo
（`10.5281/zenodo.20929034`）下载原始压缩包即可。

## 数据来源与许可

- 数据为 **TCMCPD v1.0**，**CC BY 4.0**，未做任何修改，可再分发但须署名。
- 出处与引用要求见 `NOTICE.md`；数据集自带的 `PROVENANCE.md`、`CITATION.md` 保留在
  `data/TCMCPD_TCM_Case_Records_v1.0/` 内。
- 逐文件校验和见 `CHECKSUMS.sha256`（覆盖 data 与 results）。

## 边界

- 单一语料：数字刻画该资源，不外推为普适常数；
- 关系为数据集作者从文本抽取，证型–药味关联是共现统计，不是临床因果；
- 无疗效结局字段，不作治疗效应声明。
