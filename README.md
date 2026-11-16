# code2flowchart

当前只维护一个活动主技能：`code2flowchart`。专注 C/C++ 代码转流程图、单元测试，以及接口与时序集成测试，不再维护嵌套的重复副本。

```text
MySkills/
  code2flowchart/       唯一技能入口、参考规则、脚本与测试
  .github/workflows/   回归测试工作流
  README.md
```

## 技能目录

| 技能 | 用途 | 当前状态 |
| --- | --- | --- |
| [code2flowchart](code2flowchart/SKILL.md) | C/C++ 代码转 draw.io 流程图，以及按需的单元测试、接口与时序集成测试设计 | 流程图有转换脚本；UT 生成草稿；IT/时序由 AI 依据源码设计，不自动执行硬件测试 |

仓库中只保留一个 `SKILL.md`，名称为 `code2flowchart`。流程图自检、单元测试和时序集成测试均为该技能的内部模式，细则放在 `references/`，不再分成子技能。默认只画流程图并自检，测试与 DD 都按需启用。测试设计依据见[筛选后的 UVP/ITP 规则](code2flowchart/references/code-test-checklists.md)，不包含漏洞扫描、资源盘点和发布审批。

## C 代码转流程图

需要 Python 3.10 或更高版本。从仓库根目录运行：

```bash
python code2flowchart/scripts/code2flowchart.py source.c --function target_func --svg --validate
python code2flowchart/scripts/validate.py code2flowchart/output/target_func/target_func.drawio --strict
```

默认输出位于技能目录下的 `code2flowchart/output/<函数名>/`，不随运行时的工作目录改变；可用 `--out-dir` 指定位置。`.drawio` 是正式交付文件，SVG 是预览。生成或修改后，由使用技能的 AI 按[自检规则](code2flowchart/references/flowchart-self-check.md)继续核对源码，并在具备视觉能力时实际查看最新渲染图。

默认流程不需要第三方 Python 包。`--preview` 和 `--all` 需要可选的 Pillow；没有 Pillow 时可只使用 `--svg`。详细参数和可选的 DD/UT 输出见[使用指南](code2flowchart/USAGE.md)。

导入技能时，只选择整个 `code2flowchart/` 目录，保留其中的 `SKILL.md`、`agents/`、`references/`、`scripts/`、`tests/`、`examples/` 和 `output/`，不只复制入口 MD。无需再安装自检、UT 或 IT 子技能。

## 测试

```bash
python -B -m unittest discover -s code2flowchart/tests -v
```

[测试工作流](.github/workflows/tests.yml)在推送和 Pull Request 时运行同一套测试，覆盖 Windows/Linux 与 Python 3.10/3.13。配置依据：[checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python)。自动测试不代替原生 draw.io 渲染检查、C 编译或实板验证。

[固定验收样例](code2flowchart/examples/acceptance/README.md)包含高风险 C 控制流源码，以及重试、多路返回和 `for + continue` 的结构预期、可编辑图、SVG、渲染预览与自检记录。测试会重新生成图并比对基线，不自动覆盖基线。

## 维护约定

- `code2flowchart/` 是唯一维护入口。原 `MySkills/code2flowchart/` 旧副本已合并移除；旧配置请改用根目录路径，历史内容仍可从 Git 历史查看。
- 已移除无关的 `codex-starhub/` 及其归档，不把多模型调度混入本技能；旧内容仍可从 Git 历史查看。
- 调整技能时同步核对入口说明、引用文档和实际脚本行为；修复转换问题时增加对应测试。
- Python/JavaScript/Go 的适配文件目前只是接口草稿，不代表支持这些语言，也不扩大 C/C++ 技能的使用范围。
- 生成物优先写入 `code2flowchart/output/`，该目录已忽略产物；其他 `--out-dir` 由使用者自行管理，提交前检查暂存文件。
- 不将密钥、私人文档、临时预览或未经核对的第三方代码放入技能源码。
- 当前未设置仓库级 `LICENSE`，授权方式待仓库所有者确定。
