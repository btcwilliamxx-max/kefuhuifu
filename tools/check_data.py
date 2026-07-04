#!/usr/bin/env python3
"""
check_data.py — kefuhuifu 数据完整性校验

检查项（hard errors，会让脚本返回 1）：
  1. [链接]: 后**直接**接下一条记录（没有 --- 也跳了空行）—— 这是会导致条目被吞掉的 bug
  2. [答案] 字段为空
  3. 条目数和 --- 分隔符数对不上（至少每条之间要有 ---，否则可能丢条目）

仅警告（soft warnings，不让脚本失败）：
  - 文件末尾没有 ---（解析器仍能读，但建议补上以防御 append 出错）

用法：
  python tools/check_data.py             # 校验全部 7 个 .txt
  python tools/check_data.py data/常用话术.txt  # 校验单个文件

退出码：0 = 通过（含 warning），1 = 有 hard error
"""
import sys
from pathlib import Path


EXPECTED_FILES = [
    '活动公告.txt', '提案政策.txt', '工作室事务.txt',
    '常用话术.txt', '产品操作.txt', '常见FAQ.txt', '地址合约.txt',
]


def check_file(path: Path):
    """Returns (errors, warnings) lists"""
    errors, warnings = [], []
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError as e:
        errors.append(f'ENCODING FAIL: {e}')
        return errors, warnings

    lines = text.split('\n')

    # 1. 找 [链接]: 行，检查后面接什么
    for i, line in enumerate(lines):
        if line.strip() == '[链接]:':
            next_idx = i + 1
            # skip blank lines
            while next_idx < len(lines) and lines[next_idx].strip() == '':
                next_idx += 1
            if next_idx >= len(lines):
                continue  # 文件末尾
            next_line = lines[next_idx].strip()

            if next_line.startswith('[问题') or next_line == '[问题/关键词]:':
                # ↑ 直接接下一条目：hard error
                errors.append(
                    f'line {i+1}: [链接]: 后直接接 {next_line!r}（缺 --- 分隔符）'
                )
            elif next_line != '---':
                # 往前看几行有没有 ---
                j = next_idx
                found_sep = False
                while j < len(lines):
                    if lines[j].strip() == '---':
                        found_sep = True; break
                    if lines[j].startswith('[问题'):
                        break
                    j += 1
                if not found_sep:
                    errors.append(
                        f'line {i+1}: [链接]: 后到下一条目之间没有 --- 分隔符'
                    )

    # 2. 找 --- 数 vs 条目数
    entries = [l for l in lines if l.startswith('[问题/关键词]:') or l.startswith('[问题]:')]
    n_entries = len(entries)
    sep_lines = sum(1 for l in lines if l.strip() == '---')

    # 末尾情况：clean 情况 = 文件末尾有 --- 跟空行（最后一行的 ---）
    # 末尾情况：clean 情况 = 文件末尾有 --- 跟空行（最后一行的 ---）。
    # 用 lines[-1] 还是 lines[-2] 取决于是否带 trailing newline；
    # 取最后两个 line 的「非空最近一个是 --- 吗」更稳。
    non_empty = [l for l in lines if l.strip()]
    last_non_empty = non_empty[-1].strip() if non_empty else ''
    ends_with_sep = last_non_empty == '---'

    if not ends_with_sep:
        # 软警告：解析器仍能读，但建议补上
        warnings.append(
            f'文件末尾没有 ---（推荐补上，否则 append 时容易丢条目）'
        )

    # 分隔符数：每条记录结尾都有一个 ---。如果末尾有 ---，应该 == n；
    # 否则（末尾缺 ---）应该 == n - 1。但每个 [链接]: 之间必须至少有 ---。
    if ends_with_sep:
        expected = n_entries
    else:
        expected = n_entries - 1  # 最后一条没有 ---
    if sep_lines < expected:
        errors.append(
            f'条目 {n_entries} 个，分隔符 {sep_lines} 个（少于预期 {expected}）—— 中间可能丢条目'
        )

    # 3. 每条 [答案] 非空
    blocks = []
    cur = ''
    for line in lines:
        if line.strip() == '---':
            if cur.strip(): blocks.append(cur)
            cur = ''
        else:
            cur += line + '\n'
    if cur.strip(): blocks.append(cur)

    import re
    for bi, block in enumerate(blocks):
        answer_m = re.search(r'\[答案\]:\s*(.*?)(?:\[链接\]:|\[图片\]:|$)', block, re.DOTALL)
        if not answer_m:
            errors.append(f'block {bi+1}: 缺 [答案]: 字段')
            continue
        ans = answer_m.group(1).strip()
        if not ans:
            errors.append(f'block {bi+1}: [答案] 为空')

    return errors, warnings


def main():
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        base = Path(__file__).parent.parent / 'data'
        paths = [base / f for f in EXPECTED_FILES]

    total_errors = 0
    total_warnings = 0
    for p in paths:
        if not p.exists():
            print(f'{p}: ❌ 文件不存在')
            total_errors += 1
            continue
        errs, warns = check_file(p)
        if errs:
            print(f'{p}: ❌ {len(errs)} 错误')
            for e in errs:
                print(f'  E: {e}')
            total_errors += len(errs)
        elif warns:
            print(f'{p}: ✅ OK ({len(warns)} 警告)')
            for w in warns:
                print(f'  W: {w}')
            total_warnings += len(warns)
        else:
            print(f'{p}: ✅ OK')

    print()
    if total_errors == 0:
        print(f'🎉 全部通过（{total_warnings} 个警告）' if total_warnings else '🎉 全部通过，无警告')
        return 0
    else:
        print(f'⚠ {total_errors} 个错误，{total_warnings} 个警告')
        return 1


if __name__ == '__main__':
    sys.exit(main())
