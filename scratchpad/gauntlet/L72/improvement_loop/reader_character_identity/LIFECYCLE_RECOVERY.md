# Separate lifecycle assertion correction

Original l72-reader-character-adapter ran9.785971s, exit1:19tests passed and the
lifecycle test failed its final spelling assertion. Its measured event count was
exactly1; the actual public detector schema spells the card ice_wizard, while the
test expected ice-wizard. Preserve original test_adapter.py and failed receipt.
Adapter/decoder sources and behavior stay unchanged. Run only the failed lifecycle
case in a separate test using vocab.engine_key('IceWizard') as the schema reference;
do not repeat the19completed cases or byte decoder qualification.

CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L71/integration/run_check.py --name l72-reader-character-lifecycle-v2 --expect passed -- research/ext/Royale/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L72/improvement_loop/reader_character_identity/test_lifecycle_v2.py -q
EXPECT: passed
