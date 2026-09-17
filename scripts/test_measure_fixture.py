#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_measure_fixture.py — measure.py 最小 fixture 自测（无 pytest 依赖，直接跑）。

构造 6 个假 skill（临时目录，只读输入、输出写临时目录）：
  zh-heavy       中文重（带 references）           → 断言 tokens 量级、无 flags
  en-light       英文轻（带 references）           → 断言 tokens 量级
  mega-no-refs   超重 body + 超长 description、无 refs → 断言 heavy_body_no_refs + oversized_description
  zh-heavy-copy  zh-heavy 换名跨 agent 复制件       → 断言 duplication jaccard ≥ 0.55
  tiny-skeleton  <50 行且无 refs/scripts           → 断言 skeleton
  ghost          路径不存在                        → 断言失败降级（warning + on_trigger=0，退出码 0）
另跑一遍无 usage 数据的 inventory → 断言 no_usage_data 归一路径。
跑法：python3 scripts/test_measure_fixture.py   （全过输出 PASS 后退出 0）
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import measure  # noqa: E402
from adapters import skillmd  # noqa: E402  B1：用真实 collect 侧扫描函数做防回归

ZH_DESC = '视频口播脚本技能：接收碎片思考，做选题装配，提炼要点直接成文，支持抖音和小红书双平台分发。'
ZH_BODY = '\n'.join(
    '第%d步：先把碎片思考收进来，判断这条值不值得拍，能不能立住一个观点。' % i for i in range(1, 16))
EN_DESC = 'Lightweight English helper skill for formatting notes and summaries.'
EN_BODY = '\n'.join('Line %d: the quick brown fox jumps over the lazy dog here.' % i for i in range(1, 61))
FILLER = '这段填充文本用来把正文撑过八千个token的门槛，重复出现即可，内容本身没有意义。'
MEGA_BODY = ZH_BODY + '\n' + (FILLER * 400)  # BPE 会压缩重复文本，倍数给足保证 >8000 token


def write_skill(root, name, desc, body, refs=None):
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'SKILL.md'), 'w', encoding='utf-8') as f:
        f.write('---\nname: %s\ndescription: %s\n---\n%s\n' % (name, desc, body))
    for rf in refs or []:
        p = os.path.join(d, rf)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write('参考文档：这里是一份中文参考内容，用于验证 refs_total 计量。\n' * 5)
    return d


def build_inventory(root, with_usage=True):
    paths = {
        # B1：zh-heavy 同时放一个 scripts/ 文件，让真实扫描能覆盖 scripts_files 前缀形态
        'zh-heavy': write_skill(root, 'zh-heavy', ZH_DESC, ZH_BODY,
                                ['references/guide.md', 'scripts/run.py']),
        'en-light': write_skill(root, 'en-light', EN_DESC, EN_BODY, ['references/usage.md']),
        'mega-no-refs': write_skill(root, 'mega-no-refs', ZH_DESC * 24, MEGA_BODY),
        'zh-heavy-copy': write_skill(root, 'zh-heavy-copy', ZH_DESC, ZH_BODY, ['references/guide.md']),
        'tiny-skeleton': write_skill(root, 'tiny-skeleton', EN_DESC, 'only ten lines\n' * 10),
    }
    today = date.today()
    skills = [
        dict(id='claude-code::zh-heavy', agent='claude-code', name='zh-heavy',
             path=paths['zh-heavy'], symlink_target=None, scope='user', description=ZH_DESC,
             has_skill_md=True, body_chars=len(ZH_BODY), body_lines=15,
             ref_files=['references/guide.md'], ref_total_chars=120, scripts_files=[],
             frontmatter_keys=['name', 'description']),
        dict(id='claude-code::en-light', agent='claude-code', name='en-light',
             path=paths['en-light'], symlink_target=None, scope='user', description=EN_DESC,
             has_skill_md=True, body_chars=len(EN_BODY),  # 故意缺 body_lines：测回退到实读计数
             ref_files=['references/usage.md'], ref_total_chars=200, scripts_files=[],
             frontmatter_keys=['name', 'description']),
        dict(id='claude-code::mega-no-refs', agent='claude-code', name='mega-no-refs',
             path=paths['mega-no-refs'], symlink_target=None, scope='user',
             description=ZH_DESC * 24, has_skill_md=True, body_chars=len(MEGA_BODY),
             body_lines=200, ref_files=[], ref_total_chars=0, scripts_files=[],
             frontmatter_keys=['name', 'description']),
        dict(id='codex::zh-heavy-copy', agent='codex', name='zh-heavy-copy',
             path=paths['zh-heavy-copy'], symlink_target=None, scope='user', description=ZH_DESC,
             has_skill_md=True, body_chars=len(ZH_BODY), body_lines=15,
             ref_files=['references/guide.md'], ref_total_chars=120, scripts_files=[],
             frontmatter_keys=['name', 'description']),
        dict(id='claude-code::tiny-skeleton', agent='claude-code', name='tiny-skeleton',
             path=paths['tiny-skeleton'], symlink_target=None, scope='user', description=EN_DESC,
             has_skill_md=True, body_chars=110, body_lines=10, ref_files=[], ref_total_chars=0,
             scripts_files=[], frontmatter_keys=['name', 'description']),
        dict(id='claude-code::ghost', agent='claude-code', name='ghost',
             path=os.path.join(root, 'not-exist'), symlink_target=None, scope='user',
             description=EN_DESC, has_skill_md=True, body_chars=0, body_lines=0,
             ref_files=[], ref_total_chars=0, scripts_files=[], frontmatter_keys=[]),
    ]
    inv = {'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
           'scan_seconds': 0.1, 'agents': [], 'skills': skills, 'warnings': ['原有 warning 一条']}
    if with_usage:
        inv['usage'] = {'window_days': 30, 'window_note': 'fixture', 'sessions_scanned': 87,
                        'records': [
                            {'skill_id': 'claude-code::zh-heavy', 'activations': 12,
                             'last_seen': (today - timedelta(days=1)).isoformat(),
                             'first_seen': (today - timedelta(days=28)).isoformat()},
                            {'skill_id': 'claude-code::en-light', 'activations': 90,
                             'last_seen': today.isoformat(),
                             'first_seen': (today - timedelta(days=30)).isoformat()}],
                        'coverage': {'transcripts_found': True, 'skip_env_detected': False}}
    return inv


def run_measure(inv_path, out_path):
    rc = measure.main([inv_path, '--out', out_path])
    assert rc == 0, 'measure 退出码应为 0，实际 %s' % rc
    with open(out_path, encoding='utf-8') as f:
        return json.load(f)


def case_main(tmp):
    inv_path = os.path.join(tmp, '00-inventory.json')
    with open(inv_path, 'w', encoding='utf-8') as f:
        json.dump(build_inventory(os.path.join(tmp, 'skills')), f, ensure_ascii=False)
    m = run_measure(inv_path, os.path.join(tmp, '01-metrics.json'))
    by = {s['id']: s for s in m['skills']}
    # B1 防回归①：真实 collect 侧（skillmd.scan_skill_dir）产出的 ref_files/scripts_files
    # 必须相对 skill 根带目录前缀——裸文件名会让 measure 的 join(path, rf) 全部断线
    scanned, _ = skillmd.scan_skill_dir(os.path.join(tmp, 'skills', 'zh-heavy'),
                                        'claude-code', 'user')
    assert scanned['ref_files'] == ['references/guide.md'], \
        'scan_skill_dir 应产出带 references/ 前缀的路径，实际 %s' % scanned['ref_files']
    assert scanned['scripts_files'] == ['scripts/run.py'], \
        'scripts_files 应带 scripts/ 前缀，实际 %s' % scanned['scripts_files']
    # B1 防回归②：手工构造的 inventory 数据形态必须与真实 collect 产出一致（元素须含目录前缀）
    for s in m['skills']:
        for rf in s.get('ref_files') or []:
            assert '/' in rf or os.sep in rf, \
                'fixture 的 ref_files 必须带目录前缀（如 references/），裸文件名会掩盖断线：%r' % rf
    zh, en, mega, copy, tiny, ghost = (by['claude-code::zh-heavy'], by['claude-code::en-light'],
                                       by['claude-code::mega-no-refs'], by['codex::zh-heavy-copy'],
                                       by['claude-code::tiny-skeleton'], by['claude-code::ghost'])
    # tokens 口径与量级（o200k 本地）
    for s in m['skills']:
        t = s['tokens']
        assert t['tokenizer'] == 'o200k_local' and '偏差' in t['accuracy_note']
    assert 30 < zh['tokens']['always'] < 200 and 150 < zh['tokens']['on_trigger'] < 1500
    assert zh['tokens']['refs_total'] > 0
    assert 100 < en['tokens']['on_trigger'] < 2000 and en['tokens']['on_trigger'] < mega['tokens']['on_trigger']
    assert mega['tokens']['on_trigger'] > 8000, 'mega 应超 8000 token，实际 %d' % mega['tokens']['on_trigger']
    assert zh['tokens']['on_trigger'] == copy['tokens']['on_trigger'], '同内容 body 计量应一致'
    assert ghost['tokens']['on_trigger'] == 0 and ghost['tokens']['always'] > 0
    # structure_flags
    assert zh['structure_flags'] == [] and en['structure_flags'] == []
    assert set(mega['structure_flags']) == {'heavy_body_no_refs', 'oversized_description'}
    assert len(mega['description']) > 1024, 'oversized 判据前提：description 超 1024 字符'
    assert tiny['structure_flags'] == ['skeleton']
    # duplication：zh ↔ 换名复制件（跨 agent）
    dup_ids = {d['with']: d for d in zh['duplication']}
    assert 'codex::zh-heavy-copy' in dup_ids, '应识别换名重复，实际 %s' % list(dup_ids)
    assert dup_ids['codex::zh-heavy-copy']['jaccard'] > 0.55
    assert dup_ids['codex::zh-heavy-copy']['note'] == '换名疑似重复'
    back = {d['with'] for d in copy['duplication']}
    assert 'claude-code::zh-heavy' in back, 'duplication 应双向记录'
    assert all('ghost' not in d['with'] for d in zh['duplication'])
    # usage_stats 关联
    assert zh['usage_stats'] == {'activations': 12, 'last_seen_days_ago': 1, 'daily_avg': 0.4}
    assert en['usage_stats']['daily_avg'] == 3.0 and en['usage_stats']['last_seen_days_ago'] == 0
    assert mega['usage_stats'] == {'activations': 0, 'last_seen_days_ago': None, 'daily_avg': 0.0}
    assert any('少用程度=1.00' in r for r in mega['priority']['reasons'])
    # priority：0-100、无记录者（久未用/0激活）应比高频在用且轻的得分高
    for s in m['skills']:
        assert 0 <= s['priority']['score'] <= 100 and s['priority']['reasons']
    assert mega['priority']['score'] > en['priority']['score']
    # inventory 原字段保留 + warning 追加（ghost 降级）+ meta
    assert m['generated_at'] and len(m['skills']) == 6
    assert m['warnings'][0] == '原有 warning 一条'
    assert any('ghost' in w and 'SKILL.md' in w for w in m['warnings'][1:])
    assert m['metrics_meta']['usage_dimension'] == 'available'
    print('case_main PASS：tokens/flags/duplication/usage/priority 共 %d 项断言通过' % 6)


def case_no_usage(tmp):
    inv_path = os.path.join(tmp, '00-inventory-nousage.json')
    with open(inv_path, 'w', encoding='utf-8') as f:
        json.dump(build_inventory(os.path.join(tmp, 'skills'), with_usage=False), f, ensure_ascii=False)
    m = run_measure(inv_path, os.path.join(tmp, '01-metrics-nousage.json'))
    zh = {s['id']: s for s in m['skills']}['claude-code::zh-heavy']
    assert zh['usage_stats'] is None, '无 usage 数据时 usage_stats 应为 null'
    assert any('no_usage_data' in r for r in zh['priority']['reasons'])
    assert 0 <= zh['priority']['score'] <= 100, '缺维度时按已知维度(0.5+0.2)归一应仍在 0-100'
    assert m['metrics_meta']['usage_dimension'] == 'no_usage_data'
    print('case_no_usage PASS：no_usage_data 归一路径通过（score=%d）' % zh['priority']['score'])


def case_cli_help():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'measure.py'), '--help'],
                       capture_output=True, text=True)
    assert r.returncode == 0 and '--out' in r.stdout and '--json' in r.stdout
    print('case_cli_help PASS')


def main():
    with tempfile.TemporaryDirectory(prefix='skill-auditor-fixture-') as tmp:
        case_main(tmp)
        case_no_usage(tmp)
    case_cli_help()
    print('ALL PASS — 全链路（真实 00-inventory.json → 常驻成本报告）待子代理 A 的 collect.py 产出后联测。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
