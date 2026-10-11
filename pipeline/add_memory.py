"""Attach zero-init match memory: python -m pipeline.add_memory CKPT OUT."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from pipeline.model_gen import load_model


def convert(source, destination, *, cap=256, width=64, layers=2, heads=4):
    if Path(source).resolve() == Path(destination).resolve():
        raise ValueError('conversion requires a separate output path')
    model, checkpoint = load_model(source, torch.device('cpu'))
    if checkpoint.get('architecture'):
        raise ValueError('converter is scoped to the standard GenModel architecture')
    if hasattr(model, 'history'):
        raise ValueError('checkpoint already has memory')
    if model.feature_version < 4:
        raise ValueError('memory requires the shared public observer (feature_version >=4)')
    model.add_history(cap=cap, width=width, layers=layers, heads=heads)
    checkpoint = {k: v for k, v in checkpoint.items() if k != 'rl'}
    checkpoint['model'] = model.state_dict()
    checkpoint['args'] = dict(checkpoint['args'], history_events=True, history_cap=cap)
    checkpoint['n_params'] = sum(p.numel() for p in model.parameters())
    checkpoint['memory_source'] = str(source)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, destination)
    return checkpoint


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('out', type=Path)
    parser.add_argument('--cap', type=int, default=256)
    parser.add_argument('--width', type=int, default=64)
    parser.add_argument('--layers', type=int, default=2)
    parser.add_argument('--heads', type=int, default=4)
    a = parser.parse_args(argv)
    convert(a.checkpoint, a.out, cap=a.cap, width=a.width, layers=a.layers, heads=a.heads)
    print(f'Attached zero-init public history -> {a.out}')


if __name__ == '__main__':
    main()
