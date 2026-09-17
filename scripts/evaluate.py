#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py — skill-auditor 深度层：给高嫌疑 skill 办官方对比考试（with/without 两份答卷 eval）
流程（SKILL.md「深度层」第 3 步；输出以 ../CONTRACT.md 的 02-eval-results.json 为准）：
读 <out-dir>/cases/<skill-id>/<case-name>/ case 库（prompt.md+graders/；没有 case 的 skill
报错不跑，先按 references/case-authoring.md 生成过人审）→ 组装临时 pkg 到 <out-dir>/
.eval-tmp/<id>-pkg/（plugin.json {"name":"<skill-name>-test"} + skills/<name>/ 完整副本 +
evals/<case>/；skill 源 100% 只读）→ 逐 skill 调官方 CLI（spike S3 实测，cwd=pkg、
target="."，两份答卷为 CLI 默认行为）：claude plugin eval . --runs N --max-cost-usd B
--no-publish --trust-plugin --json <raw>；超时=60+runs*300s，失败（exit 2 成本顶等）记 errors
其余继续 → 解析 raw（costUsd / cases[].arms.with|without[]（run 数组）/ aggregates）→ 机械判定
（Δ>0.1 valuable；|Δ|≤0.1 suspected_native_coverage 疑似须 Agent 复核；两份答卷均<0.5 或
Δ<-0.1 inconclusive，判定表见 case-authoring.md）→ 写 02-eval-results.json，raw 存 eval-raw/ 作
证据；prescreen 标 agent-upstream（预筛是 Agent 的活）；其余语义见 --help。"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

CLI_BIN = 'claude'
DEFAULT_RUNS = 2
DEFAULT_BUDGET = 2.0
COST_NOTE = 'CLI 报告的 list-price 估算；spike S3 实测单考题两份答卷 2runs ≈ $0.62'
COPY_IGNORE = shutil.ignore_patterns('.DS_Store', '__pycache__', '*.pyc', '.git')
# M7：以下两个判定阈值与 CONTRACT.md「判定阈值」节逐字对应，改这里必须同步改 CONTRACT
DELTA_FLAT = 0.1      # |Δ|≤此值 → suspected_native_coverage（疑似，须 Agent 复核）
LOW_SCORE = 0.5       # 两份答卷均低于此 → inconclusive（case 可能出坏，回炉）
PRESCREEN = {'verdict': 'agent-upstream',
             'reason': '预筛三出口由 Agent 按 references/audit-rubric.md 完成，脚本只做机械 eval'}


def sanitize(text):
    """文件系统/插件名安全片段（skill-id 的 :: 等替换为 _）。"""
    return ''.join(c if (c.isalnum() or c in '-_.') else '_' for c in text) or 'skill'


def now_iso():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def load_inventory(path):
    with open(path, 'r', encoding='utf-8') as f:
        inv = json.load(f)
    return {s.get('id'): s for s in (inv.get('skills') or []) if s.get('id')}


def find_cases(out_dir, skill_id):
    """扫 case 库，返回 ([(case_name, case_dir)], warnings)。只收含 prompt.md 的子目录。"""
    root = os.path.join(out_dir, 'cases', skill_id)
    cases, warns = [], []
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            continue
        if not os.path.isfile(os.path.join(d, 'prompt.md')):
            warns.append('%s/%s: 缺 prompt.md，跳过该 case' % (skill_id, name))
            continue
        cases.append((name, d))
        if not os.path.isdir(os.path.join(d, 'graders')):
            warns.append('%s/%s: 无 graders/，评分以 CLI 默认行为为准' % (skill_id, name))
    return cases, warns


def assemble_pkg(pkg_dir, skill, cases):
    """组装官方 plugin pkg（skill 目录只读，副本进临时区）。"""
    name = sanitize(skill.get('name') or skill.get('id'))
    src = skill.get('symlink_target') or skill.get('path')
    if not src or not os.path.isdir(src):
        raise OSError('skill 目录不存在：%s' % src)
    if os.path.isdir(pkg_dir):
        shutil.rmtree(pkg_dir)
    os.makedirs(os.path.join(pkg_dir, '.claude-plugin'))
    with open(os.path.join(pkg_dir, '.claude-plugin', 'plugin.json'), 'w', encoding='utf-8') as f:
        json.dump({'name': name + '-test'}, f)
    shutil.copytree(src, os.path.join(pkg_dir, 'skills', name), ignore=COPY_IGNORE)
    for cname, cdir in cases:
        shutil.copytree(cdir, os.path.join(pkg_dir, 'evals', cname), ignore=COPY_IGNORE)
    return name


def cli_command(runs, budget, raw_path):
    return [CLI_BIN, 'plugin', 'eval', '.', '--runs', str(runs), '--max-cost-usd', str(budget),
            '--no-publish', '--trust-plugin', '--json', raw_path]


def run_cli(pkg_dir, runs, budget, raw_path):
    """跑官方 CLI，返回 (ok, detail)。超时/启动失败/非零 exit 返回失败详情。"""
    limit = 60 + runs * 300
    try:
        p = subprocess.run(cli_command(runs, budget, raw_path), cwd=pkg_dir,
                           capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return False, 'CLI 超时（>%ds）被杀' % limit
    except OSError as e:
        return False, '无法启动 %s：%s' % (CLI_BIN, e)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or '').strip().splitlines()
        return False, 'CLI exit %d：%s' % (p.returncode, tail[-1] if tail else '(无输出)')
    return True, ''


def arm_mean(runs):
    """臂均分 = run.score 平均；无 run/无分数 → None。"""
    scores = [r.get('score') for r in (runs or []) if isinstance(r.get('score'), (int, float))]
    return round(sum(scores) / len(scores), 3) if scores else None


def judge(mw, mwo, delta):
    """机械判定（判定表见 case-authoring.md；最终判定权在 Agent）。"""
    if mw < LOW_SCORE and mwo < LOW_SCORE:
        return 'inconclusive', '两份答卷均低分，case 可能出坏（回炉重出，别下结论）'
    if delta > DELTA_FLAT:
        return 'valuable', 'with 明显高于 without'
    if delta < -DELTA_FLAT:
        return 'inconclusive', '反常（with<without）：先查 judge 再查 skill 是否干扰'
    return 'suspected_native_coverage', 'Δ≈0，疑似模型已原生覆盖（须人工复核）'


def parse_result(raw, raw_path):
    """raw CLI 结果 → 契约条目字段（含机械判定与证据链）。"""
    cases_out, pairs = [], []
    for c in raw.get('cases') or []:
        arms = c.get('arms') or {}
        w, wo = arm_mean(arms.get('with')), arm_mean(arms.get('without'))
        cases_out.append({'name': c.get('name') or c.get('id') or '?',
                          'with_score': w, 'without_score': wo})
        if w is not None and wo is not None:
            pairs.append((w, wo))
    if pairs:
        mw = sum(p[0] for p in pairs) / len(pairs)
        mwo = sum(p[1] for p in pairs) / len(pairs)
        delta = round(mw - mwo, 3)
        verdict, note = judge(mw, mwo, delta)
        evidence = ('with=%.2f without=%.2f Δ=%.2f（%d/%d case 两份答卷齐）%s；raw：%s（机械判定，'
                    '最终由 Agent 复核）' % (mw, mwo, delta, len(pairs), len(cases_out), note, raw_path))
    else:
        delta, verdict = None, 'inconclusive'
        evidence = '无可配对的两份答卷分数（cases=%d）；raw：%s' % (len(cases_out), raw_path)
    model = raw.get('model') or (raw.get('meta') or {}).get('model') or 'unknown'
    return {'cases': cases_out, 'delta': delta, 'verdict': verdict, 'evidence': evidence,
            'cost_usd': raw.get('costUsd'), 'duration_seconds': raw.get('durationSeconds'),
            'model': model}


def fake_result(skill_id, case_names, runs):
    """dry-run 假 CLI 结果（结构对齐 spike S3 实测），供真解析路径跑通。"""
    def arm(scores):
        return [{'score': s, 'graders': [{'name': 'check', 'passed': s >= 0.8}]} for s in scores]
    cases = []
    for i, cname in enumerate(case_names):
        w = [1.0 if (r + i) % 3 else 0.8 for r in range(runs)]
        wo = [0.4 if (r + i) % 2 else 0.2 for r in range(runs)]
        cases.append({'name': cname, 'arms': {'with': arm(w), 'without': arm(wo)},
                      'aggregates': {'delta': round(sum(w) / len(w) - sum(wo) / len(wo), 3)}})
    mean_d = round(sum(c['aggregates']['delta'] for c in cases) / len(cases), 2) if cases else 0.0
    return {'dry_run_fake': True, 'skill_id': skill_id, 'costUsd': 0.62 * max(1, len(cases)),
            'durationSeconds': 330 * max(1, len(cases)), 'cases': cases, 'aggregates': {'meanDelta': mean_d}}


def cache_valid(entry, cur_model):
    """缓存可沿用：有完整结果且模型未变（当前未知=默认未变；已知须与缓存严格相等）。"""
    if not entry or entry.get('error') or not entry.get('cases'):
        return False
    return (entry.get('model') or 'unknown') == cur_model if cur_model != 'unknown' else True


def fail(entry, errors, stage, detail):
    entry.update(error=detail, verdict='inconclusive', evidence='未完成 eval：%s' % detail)
    errors.append({'skill_id': entry['skill_id'], 'stage': stage, 'detail': detail})


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='深度评测编排：组装临时 plugin pkg 逐 skill 跑官方对比考试，写 02-eval-results.json'
                    '（契约见 CONTRACT.md）。对 skill 目录只读；预算为单 skill 硬顶传给 CLI。')
    ap.add_argument('--skills', required=True, help='逗号分隔 skill id（01-metrics.json 高嫌疑名单）')
    ap.add_argument('--inventory', default=None,
                    help='00-inventory.json（取 skill 实际目录），默认 <out-dir>/00-inventory.json（B2：随 --out-dir 联动）')
    ap.add_argument('--out-dir', default='skill-audit-output', help='输出目录（case 库 <out-dir>/cases/ 也在其中），默认：%(default)s')
    ap.add_argument('--max-cost-usd', type=float, default=DEFAULT_BUDGET, help='传 CLI 的单 skill 成本硬顶 USD，默认：%(default)s')
    ap.add_argument('--runs', type=int, default=DEFAULT_RUNS, help='每 case 每臂运行次数，默认：%(default)s')
    ap.add_argument('--skip-cached', action='store_true', help='02 已有该 skill 有效结果且模型未变（配 --model）则跳过')
    ap.add_argument('--model', default='unknown', help='当前运行时模型名（缓存比对；默认 unknown=视为未变）')
    ap.add_argument('--dry-run', action='store_true', help='不调 CLI：组装 pkg+打印命令+假结果走全链路，写 02-eval-results.dry-run.json')
    ap.add_argument('--keep-temp', action='store_true', help='保留 .eval-tmp 临时 pkg（调试）')
    ap.add_argument('--json', action='store_true', help='stdout 追加机器可读运行摘要')
    args = ap.parse_args(argv)
    if args.inventory is None:  # B2：--inventory 默认值随 --out-dir 联动（默认 out-dir 时与旧行为一致）
        args.inventory = os.path.join(args.out_dir, '00-inventory.json')

    out_dir = os.path.abspath(args.out_dir)
    raw_dir, tmp_root = os.path.join(out_dir, 'eval-raw'), os.path.join(out_dir, '.eval-tmp')
    try:
        os.makedirs(raw_dir, exist_ok=True)
    except OSError as e:
        print('evaluate.py: 输出目录写不进 %s（%s）' % (out_dir, e), file=sys.stderr)
        return 2
    try:
        index = load_inventory(args.inventory)
    except (OSError, ValueError) as e:
        print('evaluate.py: 读 inventory 失败 %s（%s）' % (args.inventory, e), file=sys.stderr)
        return 2

    old_by_id = {}
    cache_path = os.path.join(out_dir, '02-eval-results.json')
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                old_by_id = {r.get('skill_id'): r for r in (json.load(f).get('results') or [])}
        except (OSError, ValueError):
            old_by_id = {}
    cached = old_by_id if args.skip_cached else {}

    results, errors, warnings, n_cached, spent = [], [], [], 0, 0.0
    # B2：--skills 分隔宽容（逗号/空白均可；不做位置参数，保持契约清晰）
    ids = [x for x in re.split(r'[,\s]+', args.skills) if x]
    for sid in ids:
        if sid in cached and cache_valid(cached[sid], args.model):
            c = dict(cached[sid])
            c['cached'] = True
            results.append(c)
            n_cached += 1
            warnings.append('%s: 命中缓存跳过（model=%s）' % (sid, c.get('model')))
            continue
        entry = {'skill_id': sid, 'prescreen': dict(PRESCREEN), 'cases': [], 'delta': None,
                 'verdict': 'inconclusive', 'evidence': '', 'cost_usd': None, 'model': 'unknown',
                 'evaluated_at': now_iso(), 'runs': args.runs, 'duration_seconds': None, 'error': None}
        results.append(entry)
        skill = index.get(sid)
        if skill is None:
            fail(entry, errors, 'resolve', 'inventory 里找不到该 skill id（--inventory 对了吗）')
            continue
        cases, w = find_cases(out_dir, sid)
        warnings.extend(w)
        if not cases:
            fail(entry, errors, 'cases', 'case 库为空或不存在（%s）：请先按 references/'
                 'case-authoring.md 生成 case 并过人审（skill 自带 evals/ 的也先入库），再重跑'
                 % os.path.join(out_dir, 'cases', sid))
            continue
        pkg_dir = os.path.join(tmp_root, sanitize(sid) + '-pkg')
        try:
            assemble_pkg(pkg_dir, skill, cases)
        except OSError as e:
            fail(entry, errors, 'assemble', 'pkg 组装失败：%s' % e)
            continue
        raw_path = os.path.join(raw_dir, sanitize(sid) + '.json')
        print('[$ %s]（cwd=%s）' % (' '.join(cli_command(args.runs, args.max_cost_usd, raw_path)), pkg_dir), flush=True)
        if args.dry_run:
            raw = fake_result(sid, [n for n, _ in cases], args.runs)
            try:
                with open(raw_path, 'w', encoding='utf-8') as f:
                    json.dump(raw, f, ensure_ascii=False, indent=2)
            except OSError as e:
                fail(entry, errors, 'parse', 'dry-run 假结果写入失败：%s' % e)
                continue
        else:
            ok, detail = run_cli(pkg_dir, args.runs, args.max_cost_usd, raw_path)
            if not ok:
                fail(entry, errors, 'cli', detail)
                continue
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
            except (OSError, ValueError) as e:
                fail(entry, errors, 'parse', '结果 JSON 读取/解析失败：%s' % e)
                continue
        entry.update(parse_result(raw, raw_path))
        spent += entry['cost_usd'] or 0
        if not args.keep_temp:
            shutil.rmtree(pkg_dir, ignore_errors=True)
        print('eval %s: cases=%d delta=%s verdict=%s cost=%s%s' % (sid, len(cases),
              entry['delta'], entry['verdict'], entry['cost_usd'],
              '（dry-run 假数据）' if args.dry_run else ''), flush=True)

    models = {(r.get('model') or 'unknown') for r in results if not r.get('error')}
    top_model = args.model if args.model != 'unknown' else models.pop() if len(models) == 1 else 'unknown'
    if not args.dry_run:  # 分批跑时结转本次未涉及 skill 的旧结果（02 是累积账本，缓存的前提）
        results = [r for s, r in old_by_id.items() if s not in ids] + results
    out_path = os.path.join(out_dir, '02-eval-results.dry-run.json' if args.dry_run
                            else '02-eval-results.json')
    clean = [{k: v for k, v in r.items() if k != 'cached'} for r in results]  # cached 标志只描述本次
    doc = {'evaluated_at': now_iso(), 'model': top_model, 'budget_usd': args.max_cost_usd,
           'cost_note': COST_NOTE, 'runs': args.runs, 'dry_run': args.dry_run,
           'results': clean, 'errors': errors, 'warnings': warnings}
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print('evaluate.py: 写结果失败 %s（%s）' % (out_path, e), file=sys.stderr)
        return 2
    print('evaluate%s: %d skills（错误 %d，缓存跳过 %d）→ %s'
          % ('（dry-run，假数据）' if args.dry_run else '', len(results), len(errors), n_cached, out_path))
    if args.json:
        print(json.dumps({'ok': not errors, 'out': out_path, 'skills': len(results), 'errors': len(errors),
                          'cached': n_cached, 'dry_run': args.dry_run, 'total_cost_usd': round(spent, 2)},
                         ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
