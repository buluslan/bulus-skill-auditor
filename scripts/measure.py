#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure.py — skill-auditor 度量层：00-inventory.json → 01-metrics.json

对 inventory 每个 skill 追加以下字段（字段名/单位以 ../CONTRACT.md 为准，不得自行变更）：
  tokens          always=description / on_trigger=SKILL.md body(不含 frontmatter) / refs_total，
                  tiktoken o200k_base 本地计量，accuracy_note 标注偏差 ≤10%（本地实测）
  structure_flags oversized_description(>1024字符) / heavy_body_no_refs(body>8000tok且无refs)
                  / skeleton(body<50行且无refs/scripts)
  duplication     两两 Jaccard（对 name+description+body 混合分词：中文连续段 2-gram、英文 \\w+），
                  ≥0.55 记重复候选（人工确认级）；先缓存每个 skill 的 token set 再两两交并
  usage_stats     从 inventory.usage.records 关联：activations / last_seen_days_ago / daily_avg
  priority        score 0-100 = always归一×0.5 + 30天少用程度×0.3 + body重度×0.2；
                  usage 维度整体缺失时 reasons 记 no_usage_data，按已知维度权重归一

只读：inventory 与 skill 目录 100% 只读，唯一写操作是 --out 指定文件。
inventory 可能几 MB：一次性 json.load（stdlib 无流式 JSON 解析），但逐 skill 惰性读
SKILL.md/refs、用完即弃，不同时持有全部正文。
用法：python3 scripts/measure.py <00-inventory.json> [--out PATH] [--json]
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

import tiktoken

# 契约阈值（CONTRACT.md「判定阈值」节，代码直接用这些数）
OVERSIZE_DESC_CHARS = 1024     # description 超过 → oversized_description
HEAVY_BODY_TOKENS = 8000       # body 超过且无 refs → heavy_body_no_refs（也是 body 重度归一分母）
LISTING_BUDGET_TOKENS = 2000     # claude-code listing 预算 = 上下文×1%（200k→~2000 token≈官方 8000 字符，官方口径）；全部 always 之和超过 → 报告层警示（静默截断风险）。注意与 HEAVY_BODY_TOKENS 语义无关，撞数纯属巧合
SKELETON_LINES = 50            # body 少于且无 refs/scripts → skeleton
DUP_JACCARD = 0.55             # 重复候选门槛
W_ALWAYS, W_UNUSED, W_BODY = 0.5, 0.3, 0.2

CJK_RUN = re.compile(r'[㐀-䶿一-鿿豈-﫿]+')
WORD = re.compile(r'\w+')


def mixed_tokens(text):
    """混合分词（用于 Jaccard）：中文连续段拆字符 2-gram，其余段取 \\w+ 词（小写归一）。"""
    toks, pos = set(), 0
    for m in CJK_RUN.finditer(text):
        for w in WORD.findall(text[pos:m.start()]):
            toks.add(w.lower())
        seg = m.group()
        if len(seg) == 1:
            toks.add(seg)
        else:
            for i in range(len(seg) - 1):
                toks.add(seg[i:i + 2])
        pos = m.end()
    for w in WORD.findall(text[pos:]):
        toks.add(w.lower())
    return toks


def split_frontmatter(text):
    """返回 SKILL.md 去掉 frontmatter 后的 body（无 frontmatter 或未闭合则原样返回）。"""
    lines = text.lstrip('﻿').split('\n')
    if not lines or lines[0].strip() != '---':
        return '\n'.join(lines)
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return '\n'.join(lines[i + 1:])
    return '\n'.join(lines)


def _read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def measure_skill(enc, skill):
    """算单个 skill 的 tokens + structure_flags。返回 (tokens, flags, body, warnings)。"""
    warns = []
    desc = skill.get('description') or ''
    path = skill.get('path') or ''
    tokens = {
        'always': len(enc.encode_ordinary(desc)),
        'on_trigger': 0,
        'refs_total': 0,
        'tokenizer': 'o200k_local',
        'accuracy_note': '本地计量，与 Claude 官方 tokenizer 偏差 ≤10%（本地实测）',
    }
    body = ''
    if skill.get('has_skill_md', True):
        try:
            body = split_frontmatter(_read(os.path.join(path, 'SKILL.md')))
        except OSError as e:
            warns.append('%s: SKILL.md 读取失败（%s），on_trigger 记 0' % (skill.get('id'), e))
    else:
        warns.append('%s: 无 SKILL.md，on_trigger 记 0' % skill.get('id'))
    tokens['on_trigger'] = len(enc.encode_ordinary(body))
    for rf in skill.get('ref_files') or []:
        try:
            tokens['refs_total'] += len(enc.encode_ordinary(_read(os.path.join(path, rf))))
        except OSError as e:
            warns.append('%s: ref 文件读取失败 %s（%s）' % (skill.get('id'), rf, e))
    body_lines = skill.get('body_lines')
    if body_lines is None:
        body_lines = body.count('\n') + 1 if body else 0
    flags = []
    if len(desc) > OVERSIZE_DESC_CHARS:
        flags.append('oversized_description')
    if tokens['on_trigger'] > HEAVY_BODY_TOKENS and not (skill.get('ref_files') or []):
        flags.append('heavy_body_no_refs')
    if body_lines < SKELETON_LINES and not (skill.get('ref_files') or []) \
            and not (skill.get('scripts_files') or []):
        flags.append('skeleton')
    return tokens, flags, body, warns


def duplication_all(skills, bodies):
    """全量两两 Jaccard，返回与 skills 等长的 duplication 列表（双向记录，按 jaccard 降序）。"""
    tsets = [mixed_tokens(' '.join([s.get('name') or '', s.get('description') or '',
                                    bodies.get(s.get('id'), '')])) for s in skills]
    dups = [[] for _ in skills]
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            a, b = tsets[i], tsets[j]
            union = len(a | b)
            if not union:
                continue
            jac = len(a & b) / union
            if jac < DUP_JACCARD:
                continue
            si, sj = skills[i], skills[j]
            same_name = (si.get('name') or '') == (sj.get('name') or '')
            cross_agent = (si.get('agent') or '') != (sj.get('agent') or '')
            note = ('跨 agent 同名' if cross_agent else '同名') if same_name else '换名疑似重复'
            dups[i].append({'with': sj.get('id'), 'jaccard': round(jac, 3), 'note': note})
            dups[j].append({'with': si.get('id'), 'jaccard': round(jac, 3), 'note': note})
    for d in dups:
        d.sort(key=lambda x: -x['jaccard'])
    return dups


def build_usage_index(usage):
    """返回 (has_usage, records, window_days)。usage 整体缺失/没扫到会话 → 该维度不可用。"""
    if not isinstance(usage, dict):
        return False, {}, 30
    window = usage.get('window_days') or 30
    records = {r.get('skill_id'): r for r in (usage.get('records') or []) if r.get('skill_id')}
    has_usage = (usage.get('sessions_scanned') or 0) > 0
    return has_usage, records, window


def usage_stats_for(skill, has_usage, records, window, ref_date):
    """返回 (usage_stats 或 None, 少用程度 0-1 或 None)。"""
    if not has_usage:
        return None, None
    rec = records.get(skill.get('id'))
    if rec is None:  # transcripts 扫过但无记录 = 窗口内 0 次激活
        return {'activations': 0, 'last_seen_days_ago': None, 'daily_avg': 0.0}, 1.0
    acts = rec.get('activations') or 0
    days_ago = None
    if rec.get('last_seen'):
        try:
            days_ago = max(0, (ref_date - date.fromisoformat(str(rec['last_seen'])[:10])).days)
        except ValueError:
            pass
    daily = acts / window
    freq_deg = 1.0 - min(1.0, daily)              # 频率维度的少用程度
    recency_deg = min(1.0, days_ago / window) if days_ago is not None else 0.0
    stats = {'activations': acts, 'last_seen_days_ago': days_ago, 'daily_avg': round(daily, 2)}
    return stats, max(freq_deg, recency_deg)      # 少用 OR 久未用，取更显著者


def priority_for(tokens, unused, max_always):
    """score 0-100；usage 维度缺失(no_usage_data)时按已知维度权重归一。"""
    dims, weights, reasons = [], [], []
    a_norm = tokens['always'] / max_always if max_always else 0.0
    dims.append(a_norm); weights.append(W_ALWAYS)
    reasons.append('always=%dtok(归一%.2f)' % (tokens['always'], a_norm))
    if unused is None:
        reasons.append('no_usage_data（少用维度未计）')
    else:
        dims.append(unused); weights.append(W_UNUSED)
        reasons.append('30天少用程度=%.2f' % unused)
    b_heavy = min(1.0, tokens['on_trigger'] / HEAVY_BODY_TOKENS)
    dims.append(b_heavy); weights.append(W_BODY)
    reasons.append('body重度=%.2f(%dtok/8000)' % (b_heavy, tokens['on_trigger']))
    score = round(100.0 * sum(d * w for d, w in zip(dims, weights)) / sum(weights))
    return {'score': score, 'reasons': reasons}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='度量层：读 00-inventory.json，逐 skill 算 tokens/flags/duplication/priority，'
                    '写 01-metrics.json（契约见 CONTRACT.md）。对输入只读。')
    ap.add_argument('inventory', help='00-inventory.json 路径')
    ap.add_argument('--out', default='skill-audit-output/01-metrics.json',
                    help='输出路径（默认：%(default)s）')
    ap.add_argument('--json', action='store_true', help='stdout 追加机器可读的运行摘要')
    args = ap.parse_args(argv)
    try:
        with open(args.inventory, 'r', encoding='utf-8') as f:
            inv = json.load(f)
    except (OSError, ValueError) as e:
        print('measure.py: 读 inventory 失败 %s（%s）' % (args.inventory, e), file=sys.stderr)
        return 2
    try:
        enc = tiktoken.get_encoding('o200k_base')
    except Exception as e:  # 编码库不可用属致命：计量无意义，不写输出
        print('measure.py: tiktoken o200k_base 不可用（%s）' % e, file=sys.stderr)
        return 2

    skills = inv.get('skills') or []
    warnings = list(inv.get('warnings') or [])
    inherited_warns = len(warnings)  # m1：继承自 inventory 的旧 warning 数，结尾算"真新增"用
    bodies, max_always = {}, 0
    for s in skills:
        tokens, flags, body, w = measure_skill(enc, s)
        s['tokens'], s['structure_flags'] = tokens, flags
        bodies[s.get('id')] = body
        max_always = max(max_always, tokens['always'])
        warnings.extend(w)
    for s, dup in zip(skills, duplication_all(skills, bodies)):
        s['duplication'] = dup
    try:
        ref_date = datetime.fromisoformat(inv.get('generated_at') or '').date()
    except ValueError:
        ref_date = date.today()
    has_usage, records, window = build_usage_index(inv.get('usage'))
    for s in skills:
        stats, unused = usage_stats_for(s, has_usage, records, window, ref_date)
        s['usage_stats'] = stats
        s['priority'] = priority_for(s['tokens'], unused, max_always)

    always_total = sum(s['tokens']['always'] for s in skills)
    inv['measured_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
    inv['metrics_meta'] = {
        'measured_at': inv['measured_at'],
        'always_total_tokens': always_total,
        'usage_dimension': 'available' if has_usage else 'no_usage_data',
    }
    if always_total > LISTING_BUDGET_TOKENS:  # 常驻预算提醒：报告层用，不做硬判（CONTRACT）
        inv['metrics_meta']['listing_budget_note'] = (
            '全部 always 合计 %d token > 2000（≈官方 8000 字符预算，200k 上下文×1%%）：常驻 listing 成本超预算，报告层建议提示' % always_total)
    inv['warnings'] = warnings
    out_dir = os.path.dirname(os.path.abspath(args.out))
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(inv, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print('measure.py: 输出目录写不进 %s（%s）' % (args.out, e), file=sys.stderr)
        return 2
    new_warns = len(warnings) - inherited_warns  # m1：真新增 = 总数 − 继承自 inventory 的旧 warning
    print('measure: %d skills → %s（新增 warning %d 条）' % (len(skills), args.out, new_warns))
    if args.json:
        print(json.dumps({'ok': True, 'skills': len(skills), 'out': args.out,
                          'always_total_tokens': always_total,
                          'usage_dimension': inv['metrics_meta']['usage_dimension'],
                          'warnings_added': new_warns}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
