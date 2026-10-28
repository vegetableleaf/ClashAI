p='/workspace/f1fix3/ctl/core/src/main/java/org/crforge/core/battle/action/GiantBufferBuff.java'
s=open(p).read()
old='''    public int damage(int damage, int hitId, boolean crownTower) {
      if (damage < 1 || hitId == 0 || counter != columns.attackAmount() - 1) {
        return damage;
      }
'''
new='''    public int damage(int damage, int hitId, boolean crownTower) {
      if (damage < 1 || hitId == 0 || counter != columns.attackAmount() - 1) {
        return damage;
      }
      String logFile = System.getenv("F1FIX3_LOG");
      if (logFile != null) {
        try {
          java.nio.file.Files.writeString(
              java.nio.file.Path.of(logFile),
              "ADD " + owner.actionRowName() + " id=" + owner.actionId() + " proj=" + onProjectile
                  + " dmg=" + damage + " tower=" + crownTower + "\n",
              java.nio.file.StandardOpenOption.CREATE,
              java.nio.file.StandardOpenOption.APPEND);
        } catch (java.io.IOException e) {
          throw new RuntimeException(e);
        }
      }
'''
assert old in s
open(p,'w').write(s.replace(old,new))
