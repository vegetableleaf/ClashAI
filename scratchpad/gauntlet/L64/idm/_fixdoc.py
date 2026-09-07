p = "scratchpad/gauntlet/L64/idm/_transfer_probe.py"
s = open(p, encoding="utf-8").read()
old = '"different look" -- if upscaling recovers most of the gap it is a resolution problem (solvable by\nsourcing 1080p video); if it does not, it is a domain problem (needs re-labelling).'
new = ('"different look".\n\nRESULT (L64v) AND TWO CORRECTIONS TO THIS FILE\'S OWN PREMISES:\n'
       '  * Arm C IS A NO-OP and its result must not be read. YOLO letterboxes every input to imgsz=960 on\n'
       '    the longest side, so 640x360 and the 2129x1198 upscale of it arrive at the model as the SAME\n'
       '    960x540 image. C measured 1.97 dets/frame against B 2.05 because it IS B. A real resolution\n'
       '    arm has to CROP the arena region first, so the arena fills imgsz.\n'
       '  * The paragraph above is wrong about the video. bridgeblock.mp4 is not a phone screen inside a\n'
       '    landscape frame -- it is an EDITED highlight clip: a panning, zooming crop of part of the\n'
       '    arena with overlaid card-name captions, no hand and no elixir bar. The arena is at higher\n'
       '    magnification than our own capture, not lower, which is why detections did not collapse.')
assert s.count(old) == 1
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new))
print("ok")
