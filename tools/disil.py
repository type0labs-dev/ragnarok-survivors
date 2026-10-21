#!/usr/bin/env python3
"""Desmonta um método do main com anotações: nomes de chamadas (script.json) e literais de string (stringliteral.json).
Uso: disil.py main.bin dump/ 0xRVA [bytes]   (para no primeiro ret se bytes não for dado)"""
import bisect, json, struct, sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

img = open(sys.argv[1], 'rb').read(); d = sys.argv[2]
sj = json.load(open(d + '/script.json'))
ms = sorted((m['Address'], m['Name']) for m in sj['ScriptMethod']); A = [a for a, _ in ms]
lit = {x['Address']: x['Value'] for x in sj['ScriptString']}
meta = {m['Address']: m['Name'] for m in sj.get('ScriptMetadata', [])}
meta.update({m['Address']: m['Name'] for m in sj.get('ScriptMetadataMethod', [])})
start = int(sys.argv[3], 16); n = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x2000
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM); regs = {}
def nm(t):
    i = bisect.bisect_right(A, t) - 1
    return ms[i][1] if i >= 0 and t - A[i] < 0x10 else hex(t)
for ins in md.disasm(img[start:start + n], start):
    o = ins.op_str; note = ''
    p = o.replace(' ', '').split(',')
    if ins.mnemonic == 'adrp': regs[p[0]] = int(p[1][1:], 16)
    elif ins.mnemonic in ('ldr', 'add') and len(p) >= 2:
        base = p[1].strip('[]') if ins.mnemonic == 'ldr' else p[1]
        off = p[2].strip('#]') if len(p) > 2 else '0'
        if base in regs and off.startswith('0x') or (base in regs and off == '0'):
            a = regs[base] + int(off, 16)
            if a in lit: note = f'  ; "{lit[a]}"'
            elif a in meta: note = f'  ; {meta[a]}'
    if ins.mnemonic in ('bl', 'b') and o.startswith('#'): note = '  ; ' + nm(int(o[1:], 16))
    print(f'{ins.address:#x}: {ins.mnemonic} {o}{note}')
    if ins.mnemonic == 'ret' and len(sys.argv) <= 4: break
