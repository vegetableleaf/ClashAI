"""MEM-FULL plumbing hunks (exact anchors), applied to the shared working tree AND to origin/main's copy for a commit of
only these hunks (the shared checkout carries other workers' uncommitted edits in the same files).

    python -I mem_full_patch.py apply            # working tree (idempotent: skips hunks already in)
    python -I mem_full_patch.py commit OUTDIR    # OUTDIR/<path> = origin/main's file + these hunks (for safe_commit REPO=LOCAL)
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

H = {
    'pipeline/model_gen.py': [
        ('        self.mem = MemoryEncoder(self.d_c, self.global_in[0].in_features, F, N_SUM[memory_flag(version)], d, layers,\n                                 heads, zero_empty, zero_init).to(self.cell_emb.device)\n        self.mem.version = version\n        return self.mem\n',
         '        self.mem = MemoryEncoder(self.d_c, self.global_in[0].in_features, F, N_SUM[memory_flag(version)], d, layers,\n                                 heads, zero_empty, zero_init).to(self.cell_emb.device)\n        self.mem.version = version\n        return self.mem\n\n    def mem_full(self, e_max: Optional[int] = None, snap: bool = False) -> MemoryEncoder:\n        """MEM-FULL (opt-in, owner 10-30): the memory encoder reads ``e_max`` events (None = match_memory.E_MAX) and, with\n        ``snap``, the SNAP_FIELDS after each event\'s FIELDS (match_memory F_SNAP). The encoder has no positional input, so a\n        longer history needs no new weight; ``snap`` widens ``mem.ev_in`` with ZERO columns (every output identical until\n        they train). Saved as ``mem.full`` = [e_max, snap] (absent = the defaults, the state dict unchanged); a checkpoint\n        holding it rebuilds the same encoder on load. Idempotent; a snap encoder is never narrowed."""\n        from .match_memory import E_MAX, F, F_SNAP\n        mem = getattr(self, "mem", None)\n        if mem is None:\n            raise ValueError("mem_full needs the memory encoder (memory v1 / v2) first")\n        e_max = int(e_max or E_MAX)\n        if getattr(mem, "snap", False) and not snap:\n            raise ValueError("mem_full: this encoder already reads the board snapshot (snap cannot be turned off)")\n        if snap and mem.ev_in.in_features == F:\n            old = mem.ev_in\n            new = nn.Linear(F_SNAP, old.out_features).to(old.weight.device, old.weight.dtype)\n            with torch.no_grad():\n                new.weight.zero_()\n                new.weight[:, :F] = old.weight\n                new.bias.copy_(old.bias)\n            new.weight.requires_grad_(old.weight.requires_grad)\n            new.bias.requires_grad_(old.bias.requires_grad)\n            mem.ev_in = new\n            mem.cfg[0] = F_SNAP\n        if mem.ev_in.in_features != (F_SNAP if snap else F):\n            raise ValueError(f"mem_full: ev_in reads {mem.ev_in.in_features} floats, snap={snap} needs "\n                             f"{F_SNAP if snap else F}")\n        if "full" in mem._buffers:\n            mem.full.copy_(torch.tensor([e_max, int(snap)]))\n        else:\n            mem.register_buffer("full", torch.tensor([e_max, int(snap)], device=mem.cfg.device))\n        mem.e_max, mem.snap = e_max, bool(snap)\n        return mem\n'),
        ('            self.add_memory(d, layers, heads, version=ver, zero_empty="mem.zero_empty" in state_dict)\n            if (n_feat, n_sum) != (self.mem.ev_in.in_features, self.mem.summary[0].in_features - self.d_c):',
         '            self.add_memory(d, layers, heads, version=ver, zero_empty="mem.zero_empty" in state_dict)\n            if "mem.full" in state_dict:                                        # MEM-FULL e_max / snap, by content\n                self.mem_full(int(state_dict["mem.full"][0]), bool(int(state_dict["mem.full"][1])))\n            if (n_feat, n_sum) != (self.mem.ev_in.in_features, self.mem.summary[0].in_features - self.d_c):'),
        ('        if getattr(self, "mem", None) is not None and "mem.zero_empty" in state_dict and not hasattr(self.mem, "zero_empty"):\n            self.mem.register_buffer("zero_empty", torch.ones((), device=self.cell_emb.device))   # load_model(memory=...)\n',
         '        if getattr(self, "mem", None) is not None and "mem.zero_empty" in state_dict and not hasattr(self.mem, "zero_empty"):\n            self.mem.register_buffer("zero_empty", torch.ones((), device=self.cell_emb.device))   # load_model(memory=...)\n        if getattr(self, "mem", None) is not None and "mem.full" in state_dict and "full" not in self.mem._buffers:\n            self.mem_full(int(state_dict["mem.full"][0]), bool(int(state_dict["mem.full"][1])))   # load_model(memory=...)\n'),
    ],
    'pipeline/e1_eval.py': [
        ("""            self.mem, self._mem_gid = MM.MatchMemory(self.side), policy.gid""",
         """            self.mem, self._mem_gid = MM.MatchMemory(self.side, **MM.opts(policy.model.mem)), policy.gid   # MEM-FULL"""),
        ("""        m = rows_features(packed, B["mem_row_tab"], B["mem_row_t"], deck, ids, getattr(model.mem, "version", "v1"),
                          getattr(model.mem, "gid", None))       # v2: the vocabulary model_gen.attach_vocab set""",
         """        m = rows_features(packed, B["mem_row_tab"], B["mem_row_t"], deck, ids, getattr(model.mem, "version", "v1"),
                          getattr(model.mem, "gid", None),       # v2: the vocabulary model_gen.attach_vocab set
                          e_max=getattr(model.mem, "e_max", None) or 128)   # MEM-FULL (absent = match_memory.E_MAX)"""),
    ],
    'pipeline/rl_royale.py': [
        ("""        key = (getattr(model.mem, "version", "v1"), getattr(model.mem, "gid", None))
        if self.key is not None and key != self.key:""",
         """        key = (getattr(model.mem, "version", "v1"), getattr(model.mem, "gid", None),
               getattr(model.mem, "e_max", None) or 128)                 # MEM-FULL e_max (absent = E_MAX)
        if self.key is not None and key != self.key:"""),
        ("""            m = rows_features(packed, B["mem_row_tab"], B["mem_row_t"], deck, miss, key[0], key[1])""",
         """            m = rows_features(packed, B["mem_row_tab"], B["mem_row_t"], deck, miss, key[0], key[1], e_max=key[2])"""),
        ("""                              "tau_phase", "memory", "memory_aux", "memory_encoder_frozen",""",
         """                              "tau_phase", "memory", "memory_aux", "memory_encoder_frozen",
                              "memory_e_max", "memory_board_snap","""),
        ("""    if m is None and (cfg.get("memory_aux") is not None or cfg.get("memory_encoder_frozen") or cfg.get("memory_zero_empty")):
        raise SystemExit("memory_aux / memory_encoder_frozen / memory_zero_empty need memory v1 / v2")""",
         """    if m is None and (cfg.get("memory_aux") is not None or cfg.get("memory_encoder_frozen") or cfg.get("memory_zero_empty")):
        raise SystemExit("memory_aux / memory_encoder_frozen / memory_zero_empty need memory v1 / v2")
    # MEM-FULL (owner 10-30, memory/MEM_FULL.md): ``memory_e_max`` = events the memory reads (int >= 1; absent / null =
    # match_memory.E_MAX 128), ``memory_board_snap: true`` = + the board snapshot per play (match_memory.SNAP_FIELDS; the
    # encoder's new input columns start at ZERO). Absent / null / false = off, the historical hash.
    em = cfg.get("memory_e_max")
    if em is not None and (type(em) is not int or em < 1):
        raise SystemExit(f"memory_e_max must be null or an int >= 1, got {em!r}")
    if cfg.get("memory_board_snap") not in (None, False, True):
        raise SystemExit(f"memory_board_snap must be a bool or null, got {cfg['memory_board_snap']!r}")
    if m is None and (em is not None or cfg.get("memory_board_snap")):
        raise SystemExit("memory_e_max / memory_board_snap need memory v1 / v2")"""),
        ("""    if not cfg.get("memory_zero_empty"):                     # zero_empty off (absent / null / false) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "memory_zero_empty"}""",
         """    if not cfg.get("memory_zero_empty"):                     # zero_empty off (absent / null / false) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "memory_zero_empty"}
    if cfg.get("memory_e_max") is None:                      # MEM-FULL e_max off (absent / null) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "memory_e_max"}
    if not cfg.get("memory_board_snap"):                     # MEM-FULL snapshot off (absent / null / false) = the historical hash
        cfg = {k: v for k, v in cfg.items() if k != "memory_board_snap"}"""),
        ("""            if cfg.get("memory_zero_empty") and not hasattr(self.model.mem, "zero_empty"):
                self.model.mem.register_buffer("zero_empty", torch.ones((), device=self.dev))   # saved: actors / snapshots""",
         """            if cfg.get("memory_zero_empty") and not hasattr(self.model.mem, "zero_empty"):
                self.model.mem.register_buffer("zero_empty", torch.ones((), device=self.dev))   # saved: actors / snapshots
            if cfg.get("memory_e_max") is not None or cfg.get("memory_board_snap"):   # MEM-FULL: saved as mem.full
                self.model.mem_full(cfg.get("memory_e_max"), bool(cfg.get("memory_board_snap")))   # (zero new columns)
                log(f"[rl] memory_e_max {self.model.mem.e_max}, memory_board_snap {self.model.mem.snap}: "
                    f"ev_in reads {self.model.mem.ev_in.in_features} floats")"""),
        ("""                self._rows.memory_version = getattr(model.mem, "version", "v1")   # the empty rows' summary width""",
         """                self._rows.memory_version = getattr(model.mem, "version", "v1")   # the empty rows' summary width
                if "full" in model.mem._buffers:                                    # MEM-FULL: rows at the model's
                    self._rows.memory_e_max = model.mem.e_max                      # e_max / event width
                    self._rows.memory_n_f = model.mem.ev_in.in_features"""),
    ],
    'pipeline/train_memory.py': [
        ("""    model = load_model(a.init, dev, memory=a.memory)[0].eval()
    if a.zero_empty:
        model.mem.register_buffer("zero_empty", torch.ones((), device=dev))""",
         """    model = load_model(a.init, dev, memory=a.memory)[0].eval()
    if a.zero_empty:
        model.mem.register_buffer("zero_empty", torch.ones((), device=dev))
    if a.e_max or a.snap:                                 # MEM-FULL (memory/MEM_FULL.md 4): saved as mem.full
        model.mem_full(a.e_max or None, a.snap)"""),
        ("""    rows.memory_version, rows.memory_gid = a.memory, gid              # v2: + S1C_FIELDS (the tables' vocabulary)""",
         """    rows.memory_version, rows.memory_gid = a.memory, gid              # v2: + S1C_FIELDS (the tables' vocabulary)
    if a.e_max or a.snap:                                 # MEM-FULL: rows at the model's e_max / event width
        rows.memory_e_max, rows.memory_n_f = model.mem.e_max, model.mem.ev_in.in_features
        if a.snap and packed["vals"].shape[-1] != model.mem.ev_in.in_features:
            raise SystemExit("--snap needs --memory-tables built with dataset_gen memory --snap")"""),
        ("""    ap.add_argument("--val-sample", type=int, default=30000)""",
         """    ap.add_argument("--e-max", type=int, default=0, help="MEM-FULL: memory events read (0 = match_memory.E_MAX)")
    ap.add_argument("--snap", action="store_true", help="MEM-FULL: + the board snapshot per play (snap tables)")
    ap.add_argument("--val-sample", type=int, default=30000)"""),
    ],
    'pipeline/eval_gen.py': [
        ("""            m = (empty_rows(len(ids), ver) if isinstance(self.memory, str) and self.memory == "empty"
                 else rows_features(self.memory[0], self.memory[1], self.memory[2], self.a["deck_card"], ids, ver,
                                    getattr(self, "memory_gid", None)))""",
         """            em, nf = getattr(self, "memory_e_max", 128), getattr(self, "memory_n_f", None)   # MEM-FULL (absent = E_MAX)
            m = (empty_rows(len(ids), ver, em, nf or 46) if isinstance(self.memory, str) and self.memory == "empty"
                 else rows_features(self.memory[0], self.memory[1], self.memory[2], self.a["deck_card"], ids, ver,
                                    getattr(self, "memory_gid", None), e_max=em))
            if nf and m["mem_ev"].shape[-1] < nf:    # a snap model on tables without the snapshot: its fields unknown (0)
                m["mem_ev"] = np.concatenate([m["mem_ev"], np.zeros(m["mem_ev"].shape[:-1] + (nf - m["mem_ev"].shape[-1],),
                                                                     np.float32)], -1)"""),
    ],
    'pipeline/live_gen.py': [
        ("""        if mem is None or mem.side != side or getattr(self, "_mem_pub", None) is not self.public or (mem.t and t < mem.t[-1]):
            self.mem, self._mem_pub = MM.MatchMemory(side), self.public""",
         """        mem_model = getattr(getattr(self, "model", None), "mem", None)          # its version / MEM-FULL opts (no model: v1)
        if mem is None or mem.side != side or getattr(self, "_mem_pub", None) is not self.public or (mem.t and t < mem.t[-1]):
            self.mem, self._mem_pub = MM.MatchMemory(side, **MM.opts(mem_model)), self.public"""),
        ("""        mem_model = getattr(getattr(self, "model", None), "mem", None)          # its version (no model: v1 rows)
        return self.mem.features(t, self.gid, deck_ids, getattr(mem_model, "version", "v1"))""",
         """        return self.mem.features(t, self.gid, deck_ids, getattr(mem_model, "version", "v1"))"""),
    ],
    'pipeline/dataset_gen.py': [
        ("""def memory_replay(path: str, card_vocab: list) -> dict[str, Any]:""",
         """def memory_replay(path: str, card_vocab: list, snap: bool = False) -> dict[str, Any]:"""),
        ("""        tag, mems, st = replay_memories(path)""", """        tag, mems, st = replay_memories(path, snap)"""),
        ("""def replay_memories(path: str) -> tuple[str, dict, dict]:""",
         """def replay_memories(path: str, snap: bool = False) -> tuple[str, dict, dict]:"""),
        ("""        mems[s] = MM.build(s, samples, plays)""", """        mems[s] = MM.build(s, samples, plays, snap=snap)    # MEM-FULL snap: + SNAP_FIELDS"""),
        ("""def memory_tables(dataset: Path, out: Path, *, workers: int = 4, limit: int = 0, log=sys.stderr) -> dict[str, Any]:""",
         """def memory_tables(dataset: Path, out: Path, *, workers: int = 4, limit: int = 0, log=sys.stderr,
                  snap: bool = False) -> dict[str, Any]:"""),
        ("""    jobs = [(f, meta["card_vocab"]) for f in files]""",
         """    jobs = [(f, meta["card_vocab"]) + ((True,) if snap else ()) for f in files]   # MEM-FULL snap tables"""),
        ("""             "F": MM.F, "S": MM.S, "E_MAX": MM.E_MAX, "fields": list(MM.FIELDS), "groups": list(MM.GROUPS),""",
         """             "F": MM.F_SNAP if snap else MM.F, "S": MM.S, "E_MAX": MM.E_MAX,
             "fields": list(MM.FIELDS + (MM.SNAP_FIELDS if snap else ())), "groups": list(MM.GROUPS),"""),
        ("""        mp.add_argument("--limit", type=int, default=0)
        m = mp.parse_args(argv[1:])
        print(json.dumps(memory_tables(m.dataset, m.out, workers=m.workers, limit=m.limit), default=str))""",
         """        mp.add_argument("--limit", type=int, default=0)
        mp.add_argument("--snap", action="store_true", help="MEM-FULL: + the board snapshot per play (match_memory)")
        m = mp.parse_args(argv[1:])
        print(json.dumps(memory_tables(m.dataset, m.out, workers=m.workers, limit=m.limit, snap=m.snap), default=str))"""),
    ],
}


def patch(path, s):
    crlf = '\r\n' in s
    s = s.replace('\r\n', '\n')
    for a, b in H[path]:
        if (a in b and b in s) or (a not in s and b in s):
            continue                                  # already in
        assert s.count(a) == 1, (path, a[:80], s.count(a))
        s = s.replace(a, b)
    return s.replace('\n', '\r\n') if crlf else s


def main():
    if sys.argv[1] == 'apply':
        for p in H:
            f = REPO / p
            f.write_bytes(patch(p, f.read_bytes().decode('utf-8')).encode('utf-8'))
            print('applied', p)
    else:
        out = Path(sys.argv[2])
        for p in H:
            base = subprocess.run(['git', '-C', str(REPO), 'show', f'origin/main:{p}'], capture_output=True, check=True).stdout
            o = out / p
            o.parent.mkdir(parents=True, exist_ok=True)
            o.write_bytes(patch(p, base.decode('utf-8')).encode('utf-8'))
            print('wrote', o)


if __name__ == '__main__':
    main()
