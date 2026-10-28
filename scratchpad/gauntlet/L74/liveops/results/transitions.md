# Overnight transition counts

Snapshot UTC: 2026-10-28T17:47:52.794910+00:00; input bytes: 6536325.

Line numbers are 1-based and inclusive. Start lines belong to the new transition; run-stopped lines belong to the ending transition. EOF closes the final segment. Percentiles use linear interpolation at (n-1)*p. STOP takes precedence if both STOP and HANDOFF occur.

Coverage: sum of lines over all segments = 78140 == total lines = 78140: True; contiguous/nonoverlapping: True. Transitions=6189; HANDOFF=5775; STOP=84; OTHER=330; elapsed=0.449s.

Transitions containing both HANDOFF and STOP: 0. Malformed played JSON lines (retained as ordinary lines): 0.

## PRE and GAP segments

| Kind | First line | Last line | Lines |
| --- | --- | --- | --- |
| PRE | 1 | 2 | 2 |
| GAP | 410 | 414 | 5 |
| GAP | 598 | 603 | 6 |
| GAP | 745 | 746 | 2 |
| GAP | 751 | 752 | 2 |
| GAP | 7363 | 7365 | 3 |
| GAP | 9011 | 9016 | 6 |
| GAP | 10261 | 10269 | 9 |
| GAP | 10279 | 10284 | 6 |
| GAP | 10877 | 10881 | 5 |
| GAP | 12436 | 12441 | 6 |
| GAP | 12450 | 12456 | 7 |
| GAP | 12465 | 12471 | 7 |
| GAP | 12480 | 12486 | 7 |
| GAP | 12495 | 12501 | 7 |
| GAP | 12510 | 12516 | 7 |
| GAP | 12525 | 12531 | 7 |
| GAP | 12540 | 12546 | 7 |
| GAP | 12555 | 12561 | 7 |
| GAP | 12570 | 12576 | 7 |
| GAP | 12585 | 12591 | 7 |
| GAP | 16736 | 16743 | 8 |
| GAP | 17467 | 17474 | 8 |
| GAP | 18350 | 18357 | 8 |
| GAP | 18511 | 18517 | 7 |
| GAP | 18672 | 18678 | 7 |
| GAP | 18833 | 18839 | 7 |
| GAP | 18995 | 19001 | 7 |
| GAP | 19156 | 19162 | 7 |
| GAP | 19317 | 19323 | 7 |
| GAP | 19478 | 19484 | 7 |
| GAP | 19638 | 19644 | 7 |
| GAP | 19799 | 19805 | 7 |
| GAP | 20974 | 20979 | 6 |
| GAP | 21289 | 21296 | 8 |
| GAP | 24494 | 24500 | 7 |
| GAP | 24684 | 24692 | 9 |
| GAP | 24698 | 24707 | 10 |
| GAP | 25692 | 25698 | 7 |
| GAP | 28260 | 28266 | 7 |
| GAP | 28560 | 28565 | 6 |
| GAP | 28656 | 28662 | 7 |
| GAP | 29206 | 29212 | 7 |
| GAP | 33795 | 33802 | 8 |
| GAP | 33807 | 33814 | 8 |
| GAP | 34099 | 34104 | 6 |
| GAP | 40238 | 40244 | 7 |
| GAP | 40250 | 40256 | 7 |
| GAP | 40262 | 40268 | 7 |
| GAP | 40274 | 40280 | 7 |
| GAP | 47363 | 47370 | 8 |
| GAP | 55040 | 55045 | 6 |
| GAP | 55070 | 55075 | 6 |
| GAP | 55083 | 55088 | 6 |
| GAP | 57909 | 57918 | 10 |
| GAP | 58039 | 58049 | 11 |
| GAP | 58175 | 58185 | 11 |
| GAP | 58314 | 58324 | 11 |
| GAP | 58437 | 58447 | 11 |
| GAP | 58574 | 58583 | 10 |
| GAP | 58809 | 58815 | 7 |
| GAP | 58942 | 58949 | 8 |
| GAP | 59061 | 59068 | 8 |
| GAP | 60048 | 60057 | 10 |
| GAP | 60156 | 60166 | 11 |
| GAP | 60259 | 60269 | 11 |
| GAP | 60354 | 60364 | 11 |
| GAP | 60446 | 60456 | 11 |
| GAP | 60557 | 60567 | 11 |
| GAP | 60643 | 60653 | 11 |
| GAP | 60736 | 60745 | 10 |
| GAP | 67867 | 67875 | 9 |
| GAP | 68029 | 68038 | 10 |
| GAP | 68449 | 68457 | 9 |
| GAP | 68545 | 68551 | 7 |
| GAP | 73848 | 73857 | 10 |
| GAP | 73866 | 73875 | 10 |
| GAP | 73881 | 73889 | 9 |
| GAP | 73895 | 73911 | 17 |
| GAP | 73917 | 73925 | 9 |
| GAP | 73931 | 73939 | 9 |
| GAP | 73945 | 73953 | 9 |
| GAP | 73959 | 73967 | 9 |
| GAP | 73973 | 73981 | 9 |
| GAP | 77909 | 77917 | 9 |

## HANDOFF distributions

| Count | Min | Median | p90 | p99 | Max |
| --- | --- | --- | --- | --- | --- |
| unknown | 0 | 2.00 | 3.00 | 9.00 | 67 |
| tap_through input | 0 | 0.00 | 0.00 | 6.00 | 34 |
| loading | 0 | 1.00 | 1.00 | 2.00 | 4 |
| nograb | 0 | 0.00 | 0.00 | 0.00 | 2 |
| total lines | 7 | 10.00 | 16.00 | 43.26 | 124 |

## Every STOP transition

| First line | Last line | unknown | tap_through input | loading | nograb | total lines | STOP why |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 280 | 409 | 82 | 40 | 0 | 0 | 130 | 40 tap-throughs and still no known screen |
| 473 | 597 | 82 | 40 | 0 | 0 | 125 | 40 tap-throughs and still no known screen |
| 615 | 744 | 82 | 40 | 0 | 0 | 130 | 40 tap-throughs and still no known screen |
| 747 | 750 | 0 | 0 | 0 | 0 | 4 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 7354 | 7362 | 0 | 0 | 0 | 0 | 9 | transition over 300 s |
| 9007 | 9010 | 0 | 0 | 0 | 0 | 4 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 10241 | 10260 | 4 | 1 | 0 | 0 | 20 | TROPHY_ROAD_ALERT: unknown screen for 10 s after the trophy-road Choose / card tap -- not tapping blind |
| 10270 | 10278 | 2 | 0 | 0 | 0 | 9 | TROPHY_ROAD_ALERT: unknown screen for 10 s after the trophy-road Choose / card tap -- not tapping blind |
| 10772 | 10876 | 52 | 40 | 0 | 0 | 105 | 40 tap-throughs and still no known screen |
| 12430 | 12435 | 0 | 0 | 2 | 0 | 6 | loading screen for 60 s |
| 12442 | 12449 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12457 | 12464 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12472 | 12479 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12487 | 12494 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12502 | 12509 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12517 | 12524 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12532 | 12539 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12547 | 12554 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12562 | 12569 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 12577 | 12584 | 0 | 0 | 2 | 0 | 8 | loading screen for 60 s |
| 16726 | 16735 | 2 | 3 | 0 | 0 | 10 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 17410 | 17466 | 3 | 40 | 0 | 0 | 57 | 40 tap-throughs and still no known screen |
| 18196 | 18349 | 2 | 1 | 0 | 0 | 154 | transition over 300 s |
| 18358 | 18510 | 0 | 0 | 0 | 0 | 153 | transition over 300 s |
| 18518 | 18671 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 18679 | 18832 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 18840 | 18994 | 0 | 0 | 0 | 0 | 155 | transition over 300 s |
| 19002 | 19155 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 19163 | 19316 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 19324 | 19477 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 19485 | 19637 | 0 | 0 | 0 | 0 | 153 | transition over 300 s |
| 19645 | 19798 | 0 | 0 | 0 | 0 | 154 | transition over 300 s |
| 20881 | 20973 | 17 | 34 | 0 | 0 | 93 | transition over 300 s |
| 21282 | 21288 | 0 | 0 | 0 | 0 | 7 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 24416 | 24493 | 11 | 40 | 0 | 0 | 78 | 40 tap-throughs and still no known screen |
| 24679 | 24683 | 0 | 0 | 0 | 0 | 5 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 24693 | 24697 | 0 | 0 | 0 | 0 | 5 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 25638 | 25691 | 5 | 40 | 0 | 0 | 54 | 40 tap-throughs and still no known screen |
| 28252 | 28259 | 0 | 0 | 0 | 0 | 8 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 28547 | 28559 | 2 | 0 | 0 | 0 | 13 | transition over 300 s |
| 28649 | 28655 | 0 | 0 | 0 | 0 | 7 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 29201 | 29205 | 0 | 0 | 0 | 0 | 5 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 33791 | 33794 | 0 | 0 | 0 | 0 | 4 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 33803 | 33806 | 0 | 0 | 0 | 0 | 4 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 34042 | 34098 | 17 | 0 | 0 | 0 | 57 | transition over 300 s |
| 40228 | 40237 | 0 | 0 | 0 | 0 | 10 | transition over 300 s |
| 40245 | 40249 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 40257 | 40261 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 40269 | 40273 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 47290 | 47362 | 23 | 40 | 3 | 0 | 73 | 40 tap-throughs and still no known screen |
| 55028 | 55039 | 0 | 0 | 0 | 0 | 12 | transition over 300 s |
| 55046 | 55069 | 9 | 5 | 1 | 3 | 24 | screenshots failing for 60 s |
| 55076 | 55082 | 0 | 0 | 0 | 0 | 7 | transition over 300 s |
| 57779 | 57908 | 82 | 40 | 0 | 0 | 130 | 40 tap-throughs and still no known screen |
| 57919 | 58038 | 74 | 40 | 0 | 0 | 120 | 40 tap-throughs and still no known screen |
| 58050 | 58174 | 79 | 40 | 0 | 0 | 125 | 40 tap-throughs and still no known screen |
| 58186 | 58313 | 82 | 40 | 0 | 0 | 128 | 40 tap-throughs and still no known screen |
| 58325 | 58436 | 66 | 40 | 0 | 0 | 112 | 40 tap-throughs and still no known screen |
| 58448 | 58573 | 80 | 40 | 0 | 0 | 126 | 40 tap-throughs and still no known screen |
| 58686 | 58808 | 63 | 40 | 0 | 0 | 123 | 40 tap-throughs and still no known screen |
| 58816 | 58941 | 80 | 40 | 0 | 0 | 126 | 40 tap-throughs and still no known screen |
| 58950 | 59060 | 65 | 40 | 0 | 0 | 111 | 40 tap-throughs and still no known screen |
| 59975 | 60047 | 29 | 40 | 0 | 0 | 73 | 40 tap-throughs and still no known screen |
| 60058 | 60155 | 52 | 40 | 0 | 0 | 98 | 40 tap-throughs and still no known screen |
| 60167 | 60258 | 46 | 40 | 0 | 0 | 92 | 40 tap-throughs and still no known screen |
| 60270 | 60353 | 38 | 40 | 0 | 0 | 84 | 40 tap-throughs and still no known screen |
| 60365 | 60445 | 35 | 40 | 0 | 0 | 81 | 40 tap-throughs and still no known screen |
| 60457 | 60556 | 54 | 40 | 0 | 0 | 100 | 40 tap-throughs and still no known screen |
| 60568 | 60642 | 29 | 40 | 0 | 0 | 75 | 40 tap-throughs and still no known screen |
| 60654 | 60735 | 36 | 40 | 0 | 0 | 82 | 40 tap-throughs and still no known screen |
| 67859 | 67866 | 0 | 0 | 0 | 0 | 8 | transition over 300 s |
| 68018 | 68028 | 0 | 0 | 0 | 0 | 11 | transition over 300 s |
| 68426 | 68448 | 2 | 0 | 0 | 0 | 23 | transition over 300 s |
| 68532 | 68544 | 2 | 5 | 0 | 0 | 13 | ANOTHER_DEVICE: the account was opened on another device (Connection lost) |
| 73835 | 73847 | 0 | 0 | 0 | 0 | 13 | transition over 300 s |
| 73858 | 73865 | 0 | 0 | 0 | 0 | 8 | transition over 300 s |
| 73876 | 73880 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73890 | 73894 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73912 | 73916 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73926 | 73930 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73940 | 73944 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73954 | 73958 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 73968 | 73972 | 0 | 0 | 0 | 0 | 5 | transition over 300 s |
| 77903 | 77908 | 0 | 0 | 0 | 2 | 6 | screenshots failing for 60 s |

## Top 25 HANDOFF transitions by tap_through input count

Ties ordered by first line.

| First line | Last line | unknown | tap_through input | loading | nograb | total lines |
| --- | --- | --- | --- | --- | --- | --- |
| 21861 | 21932 | 12 | 34 | 0 | 0 | 72 |
| 34777 | 34840 | 4 | 34 | 0 | 0 | 64 |
| 14611 | 14721 | 67 | 32 | 1 | 0 | 111 |
| 16509 | 16576 | 24 | 32 | 0 | 0 | 68 |
| 44254 | 44323 | 6 | 32 | 0 | 0 | 70 |
| 62376 | 62499 | 62 | 31 | 1 | 0 | 124 |
| 76630 | 76678 | 4 | 31 | 0 | 0 | 49 |
| 86 | 192 | 63 | 30 | 0 | 0 | 107 |
| 26126 | 26179 | 4 | 30 | 0 | 0 | 54 |
| 30277 | 30336 | 4 | 30 | 1 | 0 | 60 |
| 33942 | 34001 | 10 | 30 | 0 | 0 | 60 |
| 28749 | 28843 | 23 | 28 | 1 | 0 | 95 |
| 39499 | 39551 | 4 | 26 | 0 | 0 | 53 |
| 13979 | 14047 | 14 | 25 | 0 | 0 | 69 |
| 6033 | 6121 | 51 | 24 | 0 | 0 | 89 |
| 53640 | 53728 | 51 | 24 | 0 | 0 | 89 |
| 43203 | 43281 | 22 | 23 | 2 | 0 | 79 |
| 56449 | 56526 | 48 | 23 | 0 | 0 | 78 |
| 59069 | 59153 | 38 | 23 | 1 | 0 | 85 |
| 49072 | 49154 | 46 | 22 | 0 | 0 | 83 |
| 64626 | 64701 | 21 | 21 | 0 | 0 | 76 |
| 25108 | 25139 | 4 | 20 | 1 | 0 | 32 |
| 20849 | 20880 | 4 | 19 | 0 | 0 | 32 |
| 1250 | 1319 | 38 | 18 | 1 | 0 | 70 |
| 7883 | 7950 | 38 | 18 | 0 | 0 | 68 |

## Old watcher: overlapping windows of 12 consecutive lines

| Window category | Rule-firing windows |
| --- | --- |
| Entirely inside one HANDOFF transition (benign) | 2478 |
| Overlap any STOP transition | 2470 |
| Other (including boundary/PRE/GAP windows) | 364 |
| All firing windows | 5312 |
| All candidate windows | 78129 |

## Stricter transition rules

| Tap_through input threshold | HANDOFF transitions | STOP transitions |
| --- | --- | --- |
| 3 | 82 | 29 |
| 5 | 72 | 28 |
| 8 | 48 | 26 |
