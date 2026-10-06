"""Prospective status and leakage controls, independent of corpus outcomes."""
import copy
import numpy as np
def checks(project_public,project_commands,history,target):
 gid={'rocket':1,'the-log':2,'mirror':3}
 def e(t,card='rocket',**kw):return dict(tick=t,side=1,card=card,accepted=True,**kw)
 # q=100, end=1000; status and target class are specified before execution.
 cases=[(0,[e(210)],[e(200)],1000),(1,[],[],1000),(2,[],[],200),
  (3,[e(210)],[e(200),e(200,'the-log')],1000),
  (4,[e(210)],[e(200,'unknown-card')],1000),
  (5,[e(210)],[e(200,'mirror')],1000),(6,[],[e(200)],1000),
  (7,[e(210),e(210,'the-log')],[e(200)],1000),
  (8,[e(210,identity_unknown=True)],[e(200)],1000),
  (9,[e(110,'the-log')],[e(90,'the-log'),e(200)],1000),
  (10,[e(210,'the-log')],[e(200)],1000),
  (11,[e(301)],[e(200)],1000),
  (12,[e(210)],[e(150),e(200)],1000),
  (13,[e(210)],[],1000),(14,[],[e(200)],220),
  (0,[e(200)],[e(200)],220),(0,[e(300)],[e(200)],1000),
  (8,[e(210,gap_before=True)],[e(200)],1000),
  (11,[e(150)],[e(200)],1000)]
 for expected,public,commands,end in cases:
  a=target(project_public(public,0,gid),project_commands(commands,0,gid),100,end,3)
  assert int(a[0])==expected,(expected,a.tolist())
  assert int(a[1])==(1 if expected==0 else -1)
 base=[e(20),e(80,'the-log')]
 prefix=history(project_public(base,0,gid),100)
 # Future/current events cannot become history; poisoned oracle not even an argument.
 future=base+[e(100,'mirror'),e(101),e(600,'the-log')]
 for actual in (history(project_public(future,0,gid),100),
  history(project_public([dict(x,hand_before=['mirror']*4,elixir=10,final_decks=['rocket']*8,target=999) for x in base],0,gid),100),
  history(project_public(base+[dict(e(90),side=0),dict(e(95),accepted=False),e(96,ability=True)],0,gid),100)):
  for x,y in zip(prefix,actual):np.testing.assert_array_equal(x,y)
 # Input depends on a genuine past public card, and retains duplicates and padding.
 altered=copy.deepcopy(base);altered[0]['card']='the-log'
 assert not np.array_equal(prefix[0],history(project_public(altered,0,gid),100)[0])
 h,ix=prefix;assert h[-2:].tolist()==[[1,80,0,0],[2,20,0,0]] and (h[:-2]==0).all()
 assert ix[-2:].tolist()==[0,1] and (ix[:-2]==-1).all()
 many=[e(i) for i in range(1,21)];assert history(project_public(many,0,gid),100)[1].tolist()==list(range(4,20))
 assert (history(project_public([e(20),e(20)],0,gid),100)[1][-2:]==[0,1]).all()
 return dict(status_fixtures=len(cases),causal_private_invariance=3,prefix_positive=4)
