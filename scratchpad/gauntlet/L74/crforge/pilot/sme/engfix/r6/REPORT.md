# ENG-FIX2_1 evidence

SME_LIB=/workspace/crforge_main/5e8089a4/tickprobe/lib; CPUs 28-53; WORKERS=12; sequential OFF then ON.

All baseline prefixes/counts verified; fresh5 OFF rebuild byte equality PASS; field gate PASS.

| Set | OFF lines | ON lines | Changed | OFF SHA256 | ON SHA256 |
|---|---:|---:|---:|---|---|
| dev | 138 | 138 | 60 | e094c402324a63e4d6585f6cd11f841ac7ef7eb920c0196bf5e68465f454f5ab | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 |
| fresh1 | 9 | 9 | 3 | d365b39c3d1f3fd78a084ef5b14c5fab58d9162466ab287263d0bab68e1f5d96 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 |
| fresh2 | 40 | 40 | 18 | 6b34fe7221c47dad29f05f2a8fef75ac4b0bc7f81a6f706e1140c5432119aa90 | 17b48c1caceee0950fb2369e11ffa58d9d97ffeac67e46edee6d0594a98333c3 |
| fresh3 | 17 | 17 | 7 | 5512160c777db7201d77d12c2a8901d4a470b601d5f3e3cbf5f2d779027f1507 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 |
| fresh4 | 78 | 78 | 40 | 9e16678732fe7bc5e5aec0c92bfeca64e28c30a95cf1b8b492c98faeed747aab | e9d5789a25b1d1e2a7858997b4523477f0e09acc2477cb53b3a10653a566353d |
| fresh5 | 15 | 15 | 6 | 00ea1059a358f8c12c2a3b8c29ffacfe9f937f49bf1bf752ed9da15d17d80068 | 8f4cb92d6d3c6f715235d6e9bf7b38374412b7da9caf08726f1656a2a288f049 |

## Changed matches

| Set | Match | Class | OFF counts / first_div | ON counts / first_div | Exact delta | Plants missed | New flags |
|---|---|---|---|---|---:|---|---|
| dev | live_play_20261026_082025 | same_class | {'exact': 53, 'div': 2715} / 256 | {'exact': 53, 'div': 2715} / 256 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_094126 | same_class | {'exact': 2536, 'torn_snap': 1} / None | {'exact': 2536, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_100018 | same_class | {'exact': 1887, 'torn_cmd': 1, 'torn_step': 1, 'div': 53} / 2286 | {'exact': 1887, 'torn_cmd': 1, 'torn_step': 1, 'div': 53} / 2286 | 0 | [] | [] |
| dev | live_play_20261026_100354 | same_class | {'exact': 2275, 'torn_step': 1, 'torn_cmd': 1} / None | {'exact': 2275, 'torn_step': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_101112 | same_class | {'exact': 2925, 'torn_step': 1, 'torn_cmd': 3, 'torn_snap': 1, 'torn_t1': 1} / None | {'exact': 2925, 'torn_step': 1, 'torn_cmd': 3, 'torn_snap': 1, 'torn_t1': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_101749 | same_class | {'exact': 1657, 'div': 13, 'torn_step': 1, 'torn_cmd': 1} / 226 | {'exact': 1657, 'div': 13, 'torn_step': 1, 'torn_cmd': 1} / 226 | 0 | [] | ['1:own_cycle_fail:6'] |
| dev | live_play_20261026_141505 | same_class | {'exact': 3000, 'torn_snap': 2, 'torn_t1': 2, 'torn_cmd': 2, 'torn_mixed': 1} / None | {'exact': 3000, 'torn_snap': 2, 'torn_t1': 2, 'torn_cmd': 2, 'torn_mixed': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_144057 | same_class | {'exact': 3029, 'torn_snap': 1, 'torn_mixed': 1, 'torn_t1': 1, 'torn_cmd': 1} / None | {'exact': 3029, 'torn_snap': 1, 'torn_mixed': 1, 'torn_t1': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_144615 | same_class | {'exact': 2806, 'torn_snap': 1, 'torn_cmd': 1} / None | {'exact': 2806, 'torn_snap': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_145247 | same_class | {'exact': 1803, 'torn_step': 1, 'torn_snap': 1, 'torn_cmd': 1} / None | {'exact': 1803, 'torn_step': 1, 'torn_snap': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_154839 | same_class | {'exact': 1807, 'torn_cmd': 1} / None | {'exact': 1807, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_155201 | same_class | {'exact': 2154} / None | {'exact': 2154} / None | 0 | [] | [] |
| dev | live_play_20261026_160930 | same_class | {'exact': 2525, 'torn_snap': 1, 'torn_t1': 1, 'torn_mixed': 1, 'div': 274} / 5211 | {'exact': 2525, 'torn_snap': 1, 'torn_t1': 1, 'torn_mixed': 1, 'div': 274} / 5211 | 0 | [] | ['1:own_cycle_fail:43'] |
| dev | live_play_20261026_161448 | same_class | {'exact': 130, 'div': 1635} / 372 | {'exact': 130, 'div': 1635} / 372 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_162012 | same_class | {'exact': 1739, 'torn_cmd': 1} / None | {'exact': 1739, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_165839 | same_class | {'exact': 1966, 'torn_cmd': 1} / None | {'exact': 1966, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_170912 | same_class | {'exact': 1821, 'torn_cmd': 2} / None | {'exact': 1821, 'torn_cmd': 2} / None | 0 | [] | [] |
| dev | live_play_20261026_171753 | same_class | {'exact': 3033, 'torn_late': 1, 'torn_step': 4, 'torn_snap': 2} / None | {'exact': 3033, 'torn_late': 1, 'torn_step': 4, 'torn_snap': 2} / None | 0 | [] | [] |
| dev | live_play_20261026_172835 | same_class | {'exact': 2734, 'torn_mixed': 1} / None | {'exact': 2734, 'torn_mixed': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_174147 | same_class | {'exact': 149, 'div': 2777} / 192 | {'exact': 149, 'div': 2777} / 192 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_181217 | same_class | {'exact': 2993, 'torn_cmd': 2, 'torn_hidden': 28} / None | {'exact': 2993, 'torn_cmd': 2, 'torn_hidden': 28} / None | 0 | [] | [] |
| dev | live_play_20261026_194213 | same_class | {'exact': 100, 'div': 1666} / 351 | {'exact': 100, 'div': 1666} / 351 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_194858 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| dev | live_play_20261026_202455 | same_class | {'exact': 1710, 'torn_step': 1, 'div': 483} / 3573 | {'exact': 1710, 'torn_step': 1, 'div': 483} / 3573 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_203752 | same_class | {'exact': 2328, 'torn_step': 1} / None | {'exact': 2328, 'torn_step': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_204837 | same_class | {'exact': 255, 'div': 1510} / 660 | {'exact': 255, 'div': 1510} / 660 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| dev | live_play_20261026_205934 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| dev | live_play_20261026_210249 | same_class | {'exact': 2495, 'torn_step': 1} / None | {'exact': 2495, 'torn_step': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_210720 | same_class | {'exact': 3015, 'torn_cmd': 4} / None | {'exact': 3015, 'torn_cmd': 4} / None | 0 | [] | [] |
| dev | live_play_20261026_211757 | same_class | {'exact': 1764, 'torn_step': 1} / None | {'exact': 1764, 'torn_step': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_212111 | same_class | {'exact': 2741, 'torn_cmd': 1, 'torn_mixed': 1, 'torn_t1': 2, 'torn_step': 2} / None | {'exact': 2741, 'torn_cmd': 1, 'torn_mixed': 1, 'torn_t1': 2, 'torn_step': 2} / None | 0 | [] | [] |
| dev | live_play_20261026_214710 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| dev | live_play_20261026_215757 | same_class | {'exact': 3021, 'torn_step': 1, 'torn_t1': 1} / None | {'exact': 3021, 'torn_step': 1, 'torn_t1': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_221926 | same_class | {'exact': 1764, 'torn_cmd': 1} / None | {'exact': 1764, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_222240 | same_class | {'exact': 1761, 'torn_cmd': 2, 'torn_t1': 1, 'torn_step': 1} / None | {'exact': 1761, 'torn_cmd': 2, 'torn_t1': 1, 'torn_step': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_223723 | same_class | {'exact': 1765, 'torn_cmd': 1} / None | {'exact': 1765, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_225213 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| dev | live_play_20261026_230512 | same_class | {'exact': 2391, 'torn_cmd': 2, 'torn_t1': 1, 'div': 252} / 4942 | {'exact': 2391, 'torn_cmd': 2, 'torn_t1': 1, 'div': 252} / 4942 | 0 | [] | ['1:own_cycle_fail:41'] |
| dev | live_play_20261026_233436 | same_class | {'exact': 3041, 'torn_cmd': 3, 'torn_mixed': 1, 'torn_snap': 2} / None | {'exact': 3041, 'torn_cmd': 3, 'torn_mixed': 1, 'torn_snap': 2} / None | 0 | [] | [] |
| dev | live_play_20261026_233957 | same_class | {'exact': 3034, 'torn_t1': 1, 'torn_cmd': 2, 'torn_snap': 1} / None | {'exact': 3034, 'torn_t1': 1, 'torn_cmd': 2, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_234837 | same_class | {'exact': 3029, 'torn_t1': 4, 'torn_mixed': 1, 'torn_cmd': 1} / None | {'exact': 3029, 'torn_t1': 4, 'torn_mixed': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_235355 | same_class | {'exact': 3031, 'torn_snap': 1} / None | {'exact': 3031, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261026_235915 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| dev | live_play_20261027_000233 | same_class | {'exact': 3038, 'torn_snap': 3} / None | {'exact': 3038, 'torn_snap': 3} / None | 0 | [] | [] |
| dev | live_play_20261027_001702 | same_class | {'exact': 1765, 'torn_mixed': 1} / None | {'exact': 1765, 'torn_mixed': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_002021 | same_class | {'exact': 2160, 'torn_snap': 1} / None | {'exact': 2160, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_002429 | same_class | {'exact': 3041, 'torn_step': 1} / None | {'exact': 3041, 'torn_step': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_004550 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| dev | live_play_20261027_004901 | same_class | {'exact': 2871, 'torn_step': 1, 'torn_t1': 1} / None | {'exact': 2871, 'torn_step': 1, 'torn_t1': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_014151 | same_class | {'exact': 2146} / None | {'exact': 2146} / None | 0 | [] | [] |
| dev | live_play_20261027_020134 | same_class | {'exact': 2360, 'torn_step': 2, 'torn_cmd': 1} / None | {'exact': 2360, 'torn_step': 2, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_021852 | same_class | {'exact': 1545, 'torn_cmd': 2, 'torn_snap': 1} / None | {'exact': 1545, 'torn_cmd': 2, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_022149 | same_class | {'exact': 1815, 'torn_snap': 1, 'torn_cmd': 1} / None | {'exact': 1815, 'torn_snap': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_023451 | same_class | {'exact': 847, 'div': 1086} / 1372 | {'exact': 847, 'div': 1086} / 1372 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| dev | live_play_20261027_023839 | same_class | {'exact': 1368, 'torn_step': 1, 'div': 397} / 2889 | {'exact': 1368, 'torn_step': 1, 'div': 397} / 2889 | 0 | [] | [] |
| dev | live_play_20261027_030951 | same_class | {'exact': 1764, 'torn_snap': 1} / None | {'exact': 1764, 'torn_snap': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_032352 | same_class | {'exact': 3037, 'torn_cmd': 1} / None | {'exact': 3037, 'torn_cmd': 1} / None | 0 | [] | [] |
| dev | live_play_20261027_033729 | same_class | {'exact': 2379} / None | {'exact': 2379} / None | 0 | [] | [] |
| dev | live_play_20261027_041141 | same_class | {'exact': 2379} / None | {'exact': 2379} / None | 0 | [] | [] |
| dev | live_play_20261027_041602 | same_class | {'exact': 2052, 'torn_step': 2, 'torn_mixed': 1, 'torn_cmd': 1} / None | {'exact': 2052, 'torn_step': 2, 'torn_mixed': 1, 'torn_cmd': 1} / None | 0 | [] | [] |
| fresh1 | live_play_20261028_003008 | same_class | {'exact': 3031, 'torn_cmd': 2, 'torn_t1': 2} / None | {'exact': 3031, 'torn_cmd': 2, 'torn_t1': 2} / None | 0 | [] | [] |
| fresh1 | live_play_20261028_010318 | same_class | {'exact': 46, 'div': 2330} / 242 | {'exact': 46, 'div': 2330} / 242 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh1 | live_play_20261028_010824 | same_class | {'exact': 2091, 'torn_step': 1} / None | {'exact': 2091, 'torn_step': 1} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_080427 | same_class | {'exact': 495, 'div': 1271} / 1139 | {'exact': 495, 'div': 1271} / 1139 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh2 | live_play_20261028_081253 | same_class | {'exact': 3038} / None | {'exact': 3038} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_083923 | same_class | {'exact': 1814, 'torn_hidden': 41} / None | {'exact': 1814, 'torn_hidden': 41} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_084638 | same_class | {'exact': 2065, 'div': 412} / 4285 | {'exact': 2065, 'div': 412} / 4285 | 0 | [] | ['0:own_cycle_fail:31'] |
| fresh2 | live_play_20261028_085416 | same_class | {'exact': 2359} / None | {'exact': 2359} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_095125 | same_class | {'exact': 1761} / None | {'exact': 1761} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_095444 | same_class | {'exact': 2268} / None | {'exact': 2268} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_100341 | same_class | {'exact': 1758} / None | {'exact': 1758} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_101018 | same_class | {'exact': 2905, 'div': 121} / 5968 | {'exact': 2905, 'div': 121} / 5968 | 0 | [] | [] |
| fresh2 | live_play_20261028_103056 | same_class | {'exact': 116, 'div': 1644} / 386 | {'exact': 116, 'div': 1644} / 386 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh2 | live_play_20261028_103409 | same_class | {'exact': 2839} / None | {'exact': 2839} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_110715 | same_class | {'exact': 2660} / None | {'exact': 2660} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_111523 | same_class | {'exact': 1763} / None | {'exact': 1763} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_120054 | same_class | {'exact': 478, 'div': 1092, 'torn_t1': 192, 'torn_step': 1} / 289 | {'exact': 478, 'div': 1092, 'torn_t1': 192, 'torn_step': 1} / 289 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh2 | live_play_20261028_120406 | same_class | {'exact': 2744} / None | {'exact': 2744} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_120902 | same_class | {'exact': 751, 'div': 2285} / 1653 | {'exact': 751, 'div': 2285} / 1653 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh2 | live_play_20261028_125629 | same_class | {'exact': 3022} / None | {'exact': 3022} / None | 0 | [] | [] |
| fresh2 | live_play_20261028_130522 | same_class | {'exact': 123, 'div': 1642} / 397 | {'exact': 123, 'div': 1642} / 397 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| fresh3 | live_play_20261028_131923 | same_class | {'exact': 3011} / None | {'exact': 3011} / None | 0 | [] | [] |
| fresh3 | live_play_20261028_132440 | same_class | {'exact': 2276} / None | {'exact': 2276} / None | 0 | [] | [] |
| fresh3 | live_play_20261028_133211 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| fresh3 | live_play_20261028_141254 | same_class | {'exact': 3028, 'torn_late': 8} / None | {'exact': 3028, 'torn_late': 8} / None | 0 | [] | [] |
| fresh3 | live_play_20261028_143825 | same_class | {'exact': 89, 'div': 1677} / 328 | {'exact': 89, 'div': 1677} / 328 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| fresh3 | live_play_20261028_144727 | same_class | {'exact': 121, 'div': 1643} / 393 | {'exact': 121, 'div': 1643} / 393 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh3 | live_play_20261028_145247 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_151109 | fixed | {'exact': 2767, 'div': 264} / 925 | {'exact': 3031} / None | 264 | [] | [] |
| fresh4 | live_play_20261028_152022 | same_class | {'exact': 3029} / None | {'exact': 3029} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_152540 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_153755 | same_class | {'exact': 2401} / None | {'exact': 2401} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_160144 | same_class | {'exact': 2130} / None | {'exact': 2130} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_162534 | same_class | {'exact': 2763} / None | {'exact': 2763} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_163354 | same_class | {'exact': 2387} / None | {'exact': 2387} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_165724 | same_class | {'exact': 2209} / None | {'exact': 2209} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_171948 | same_class | {'exact': 77, 'div': 1689} / 305 | {'exact': 77, 'div': 1689} / 305 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261028_172508 | same_class | {'exact': 2628} / None | {'exact': 2628} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_172955 | same_class | {'exact': 2630} / None | {'exact': 2630} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_174806 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_180343 | same_class | {'exact': 2809} / None | {'exact': 2809} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_181209 | same_class | {'exact': 155, 'torn_late': 3, 'div': 2634} / 458 | {'exact': 155, 'torn_late': 3, 'div': 2634} / 458 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261028_184534 | same_class | {'exact': 2643} / None | {'exact': 2643} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_194024 | same_class | {'exact': 257, 'div': 1489} / 663 | {'exact': 257, 'div': 1489} / 663 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261028_194921 | same_class | {'exact': 1763} / None | {'exact': 1763} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_200424 | same_class | {'exact': 1325, 'div': 441} / 2802 | {'exact': 1325, 'div': 441} / 2802 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261028_203126 | same_class | {'exact': 1764} / None | {'exact': 1764} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_203444 | same_class | {'exact': 1765} / None | {'exact': 1765} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_204439 | same_class | {'exact': 2547} / None | {'exact': 2547} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_210016 | same_class | {'exact': 1953, 'div': 44} / 2068 | {'exact': 1953, 'div': 28, 'torn_hidden': 16} / 2068 | 0 | [] | [] |
| fresh4 | live_play_20261028_213421 | same_class | {'exact': 134, 'div': 1631} / 419 | {'exact': 134, 'div': 1631} / 419 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261028_220244 | same_class | {'exact': 3025} / None | {'exact': 3025} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_222707 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_223022 | same_class | {'exact': 3028} / None | {'exact': 3028} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_223547 | same_class | {'exact': 3014} / None | {'exact': 3014} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_224625 | same_class | {'exact': 2222} / None | {'exact': 2222} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_225340 | same_class | {'exact': 1797} / None | {'exact': 1797} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_230352 | same_class | {'exact': 379, 'div': 1383} / 914 | {'exact': 379, 'div': 1383} / 914 | 0 | [] | [] |
| fresh4 | live_play_20261028_232157 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_232834 | same_class | {'exact': 3041} / None | {'exact': 3041} / None | 0 | [] | [] |
| fresh4 | live_play_20261028_235834 | same_class | {'exact': 2230, 'div': 41} / 4612 | {'exact': 2230, 'div': 41} / 4612 | 0 | [] | [] |
| fresh4 | live_play_20261029_000242 | same_class | {'exact': 3028} / None | {'exact': 3028} / None | 0 | [] | [] |
| fresh4 | live_play_20261029_000804 | same_class | {'exact': 1763} / None | {'exact': 1763} / None | 0 | [] | [] |
| fresh4 | live_play_20261029_001538 | same_class | {'exact': 56, 'div': 1709} / 263 | {'exact': 56, 'div': 1709} / 263 | 0 | [] | ['0:opp_no_fitting_deal:0'] |
| fresh4 | live_play_20261029_001856 | same_class | {'exact': 1503, 'div': 126} / 3159 | {'exact': 1503, 'div': 126} / 3159 | 0 | [] | [] |
| fresh4 | live_play_20261029_002202 | same_class | {'exact': 1766} / None | {'exact': 1766} / None | 0 | [] | [] |
| fresh4 | live_play_20261029_002515 | same_class | {'exact': 1767} / None | {'exact': 1767} / None | 0 | [] | [] |
| fresh4 | live_play_20261029_003649 | same_class | {'exact': 190, 'div': 1624} / 528 | {'exact': 190, 'div': 1624} / 528 | 0 | [] | ['1:opp_no_fitting_deal:0'] |
| fresh5 | live_play_20261029_004719 | same_class | {'exact': 1210, 'div': 570} / 2573 | {'exact': 1210, 'div': 570} / 2573 | 0 | [] | [] |
| fresh5 | live_play_20261029_011004 | same_class | {'exact': 2948} / None | {'exact': 2948} / None | 0 | [] | [] |
| fresh5 | live_play_20261029_011517 | same_class | {'exact': 1865} / None | {'exact': 1865} / None | 0 | [] | [] |
| fresh5 | live_play_20261029_014019 | same_class | {'exact': 2537} / None | {'exact': 2537} / None | 0 | [] | [] |
| fresh5 | live_play_20261029_015549 | same_class | {'exact': 1834} / None | {'exact': 1834} / None | 0 | [] | [] |
| fresh5 | live_play_20261029_021629 | same_class | {'exact': 3029} / None | {'exact': 3029} / None | 0 | [] | [] |

## Expected outcomes
- live_play_20261028_151109: PASS; class=fixed; counts={'exact': 3031}; first_div OFF=925 ON=None.
- live_play_20261028_210016: EXPECTATION NOT MET; class=same_class; counts={'exact': 1953, 'div': 28, 'torn_hidden': 16}; first_div OFF=2068 ON=2068.

Class totals: {'fixed': 1, 'regressed': 0, 'improved': 0, 'same_class': 133}
Rows: 134
Plants missed: []
Added flags: []
Nonempty ON flags: 26

Full non-plays changes: changes.txt. Full required per-match fields: table.txt and table.json. Upload hashes: upload_sha256.txt. All 12 upload hashes match. All 12 collected EF6 logs end with their done marker, with no traceback, and all result files have exact changed-match coverage.

STATUS: DONE
