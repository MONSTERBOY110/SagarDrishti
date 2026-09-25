# Speak a text file to a WAV with a Windows OneCore voice.
#
# Used by tools/record_demo.mjs to put the app's own read-aloud into the demo
# video. The browser's speechSynthesis on Windows speaks through these same
# OneCore voices, and a screen grabber cannot hear it (there is no loopback
# device on the demo laptop), so the recorder logs WHEN the app spoke and WHAT
# it said, and this renders exactly that text with exactly that voice.
#
#   powershell -File tools/tts_winrt.ps1 -TextFile in.txt -Out out.wav [-Voice Heera]

param(
  [Parameter(Mandatory = $true)][string]$TextFile,
  [Parameter(Mandatory = $true)][string]$Out,
  [string]$Voice = "Heera"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and
  $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1

function Await($op, [Type]$type) {
  $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
  $task.Wait()
  $task.Result
}

$text = [IO.File]::ReadAllText($TextFile, [Text.Encoding]::UTF8)
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$pick = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
  Where-Object { $_.DisplayName -like "*$Voice*" } | Select-Object -First 1
if ($null -eq $pick) { throw "no OneCore voice matching '$Voice'" }
$synth.Voice = $pick

$stream = Await ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
$size = [uint32]$stream.Size
$null = Await ($reader.LoadAsync($size)) ([uint32])
$bytes = New-Object byte[] $size
$reader.ReadBytes($bytes)
[IO.File]::WriteAllBytes($Out, $bytes)
Write-Output "$($pick.DisplayName): $size bytes -> $Out"
