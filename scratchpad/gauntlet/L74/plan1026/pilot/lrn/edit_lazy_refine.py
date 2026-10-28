import sys
p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(old, new):
    global s
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    assert s.count(old) == 1, (old[:70], s.count(old))
    s = s.replace(old, new)


rep('''        if getattr(self, "cell_refine", None) is not None:
            enc = dict(enc, cell_feat=self.cell_refine.features(enc["u"], tok[..., 4:6], b["mask"]))
        tr = getattr(self, "tower_refine", None)
        if tr is not None and tr.use_cell:
            enc = dict(enc, tower_cell_feat=tr.cell_feat(b["sc"]))
        return enc''', '''        lazy = getattr(self, "lazy_refine", False)          # LOOP-LRN opt-in (the RL learner): the cell-only refine
        if getattr(self, "cell_refine", None) is not None:  # features are built in cell_logits_gen, on its rows only
            enc = dict(enc, **({"refine_xy": tok[..., 4:6], "refine_mask": b["mask"]} if lazy else
                               {"cell_feat": self.cell_refine.features(enc["u"], tok[..., 4:6], b["mask"])}))
        tr = getattr(self, "tower_refine", None)
        if tr is not None and tr.use_cell:
            enc = dict(enc, **({"refine_sc": b["sc"]} if lazy else {"tower_cell_feat": tr.cell_feat(b["sc"])}))
        return enc''')
rep('''        if "cell_feat" in enc:
            logits = logits + self.cell_refine.residual(enc["cell_feat"], q)
        if "tower_cell_feat" in enc:
            logits = logits + self.tower_refine.cell.residual(enc["tower_cell_feat"], q)''', '''        if "refine_xy" in enc:                              # lazy_refine: the same features, these rows only
            enc = dict(enc, cell_feat=self.cell_refine.features(enc["u"], enc["refine_xy"], enc["refine_mask"]))
        if "refine_sc" in enc:
            enc = dict(enc, tower_cell_feat=self.tower_refine.cell_feat(enc["refine_sc"]))
        if "cell_feat" in enc:
            logits = logits + self.cell_refine.residual(enc["cell_feat"], q)
        if "tower_cell_feat" in enc:
            logits = logits + self.tower_refine.cell.residual(enc["tower_cell_feat"], q)''')
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
