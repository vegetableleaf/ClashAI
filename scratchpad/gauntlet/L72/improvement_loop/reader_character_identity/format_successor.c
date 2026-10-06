#define main original_sampler_main
#include "/mnt/c/Users/benpe/ClashBot/scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/live_sampler3.c"
#undef main

int main(void) {
 EntityFrame e={.address=0x1234,.category=5000001,.kind=15,.side=1,.x=3000,.y=17000,.card_id=203000023,.level=14,.hp=753,.max_hp=911,.behavior=2};
 emit_extended_entity(&e); putchar('\n');
 e.card_id=13000043; emit_extended_entity(&e); putchar('\n');
 e.card_id=26000000; emit_extended_entity(&e); putchar('\n');return 0;
}
