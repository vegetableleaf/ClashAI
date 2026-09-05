Add-Type -AssemblyName System.Speech
$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine([System.Globalization.CultureInfo]"en-US")
$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$rec.SetInputToWaveFile("C:\Users\benpe\ClashBot\scratchpad\bb\audio.wav")
$rec.InitialSilenceTimeout = [TimeSpan]::FromSeconds(30)
$rec.EndSilenceTimeout = [TimeSpan]::FromSeconds(0.5)
$out = New-Object System.Collections.Generic.List[string]
$n = 0
while ($true) {
  try { $r = $rec.Recognize() } catch { $out.Add("[END] " + $_.Exception.Message.Substring(0,40)); break }
  if ($null -eq $r) { $n++; if ($n -gt 3) { break } else { continue } }
  $t = [math]::Round($r.Audio.AudioPosition.TotalSeconds)
  $out.Add("[$t] " + $r.Text)
  $out | Out-File -Encoding utf8 "C:\Users\benpe\ClashBot\scratchpad\bb\transcript.txt"
}
$out | Out-File -Encoding utf8 "C:\Users\benpe\ClashBot\scratchpad\bb\transcript.txt"
"lines: " + $out.Count
