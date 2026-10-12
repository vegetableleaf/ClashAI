"""Selection, labels and the public-information boundary, with negative controls."""
import json
import unittest
from build import HERE, public_events, outcome
from fit import date_split


class TestData(unittest.TestCase):
    def test_frame_private_poison_has_no_effect(self):
        root=HERE/"test_tmp";root.mkdir(exist_ok=True)
        a={"event":"frame","tick":200,"my_side":0,"ents":[[1,1000,2000,26000000,10,20,14,123]],
           "opp_elixir_true_EVAL_ONLY":1,"opponent_hand":[1,2,3,4]}
        b=dict(a,opp_elixir_true_EVAL_ONLY="POISON_DO_NOT_USE",opponent_hand=["POISON_DO_NOT_USE"])
        one=root/"public_a.jsonl";two=root/"public_b.jsonl"
        one.write_text(json.dumps(a)+"\n");two.write_text(json.dumps(b)+"\n")
        self.assertNotEqual(a,b)  # positive control: inputs really differ
        self.assertEqual(list(public_events(one)),list(public_events(two)))
        self.assertNotIn("POISON_DO_NOT_USE",json.dumps(list(public_events(two))))

    def test_scorecard_labels_and_draw_drop(self):
        bodies=[]
        for side in (0,1):
            for x,y in ((9000,3000 if side==0 else 29000),(3500,6500 if side==0 else 25500),(14500,6500 if side==0 else 25500)):
                bodies.append(dict(card_id=-1,side=side,x=x,y=y,hp=100))
        d={"decisions":[{"side":0,"bodies":bodies}]}
        self.assertIsNone(outcome(d))
        bodies[4]["hp"]=0;self.assertEqual(outcome(d),1)
        bodies[1]["hp"]=0;self.assertIsNone(outcome(d))
        bodies[2]["hp"]=0;self.assertEqual(outcome(d),0)

    def test_latest_date_block_is_not_random_rows(self):
        records=[{"file":f"live_play_2026100{day}_{i:06d}.jsonl"} for day,n in ((8,10),(9,5)) for i in range(n)]
        records += [{"file":f"live_play_20261010_{i:06d}.jsonl"} for i in range(4)]
        self.assertEqual(date_split(records),"20261010")


if __name__=="__main__":unittest.main()
