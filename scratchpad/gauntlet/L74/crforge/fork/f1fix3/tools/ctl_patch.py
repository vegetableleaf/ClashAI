p='/workspace/f1fix3/ctl/core/src/main/java/org/crforge/core/battle/action/GiantBufferBuff.java'
s=open(p).read()
old='''    private int added(boolean crownTower) {
'''
new='''    private int added(boolean crownTower) {
      String ctl = System.getenv("F1FIX3_CTL");
      if (ctl != null && java.util.Arrays.asList(ctl.split(",")).contains(owner.actionRowName())) {
        return 0;
      }
'''
assert old in s
open(p,'w').write(s.replace(old,new))
