import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(r"C:\Jarvis")

APP = (
    ROOT
    / "workstation"
    / "jarvis_os_v3_assets"
    / "app.js"
)

SERVICE = (
    ROOT
    / "workstation"
    / "native_voice"
    / "JarvisVoiceService.cs"
)

LAUNCHER = (
    ROOT
    / "start_jarvis_native_voice.ps1"
)

BAT = (
    ROOT
    / "JARVIS.bat"
)


class VoiceV32HybridTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.app = APP.read_text(
            encoding="utf-8"
        )

        cls.service = SERVICE.read_text(
            encoding="utf-8"
        )

        cls.launcher = LAUNCHER.read_text(
            encoding="utf-8"
        )

        cls.bat = BAT.read_text(
            encoding="utf-8"
        )


    def test_hybrid_marker_present(self):

        self.assertIn(
            "JARVIS_V32_HYBRID_VOICE",
            self.app,
        )


    def test_browser_dictation_is_suspended_during_tts(self):

        self.assertIn(
            "function suspendRecognition(",
            self.app,
        )

        self.assertIn(
            "suspendRecognition();",
            self.app,
        )

        self.assertIn(
            "J.speaking",
            self.app[
                self.app.find(
                    "function startListening("
                ):
                self.app.find(
                    "// ========================================================\n    // RESPONSE EXTRACTION"
                )
            ],
        )


    def test_no_tts_restart_loop_while_speaking(self):

        onstart = self.app[
            self.app.find(
                "utterance.onstart"
            ):
            self.app.find(
                "utterance.onend"
            )
        ]

        self.assertNotIn(
            "scheduleListen(",
            onstart,
        )


    def test_native_state_bridge(self):

        self.assertIn(
            '"/state"',
            self.app,
        )

        self.assertIn(
            "nativeSpeakingState(",
            self.app,
        )

        self.assertIn(
            '"/events?after="',
            self.app,
        )


    def test_native_service_is_control_only_while_speaking(self):

        self.assertIn(
            "if (isSpeaking)",
            self.service,
        )

        speaking_gate = self.service[
            self.service.find(
                "if (isSpeaking)"
            ):
            self.service.find(
                'AddEvent(\n                            "wake"',
            )
        ]

        self.assertIn(
            "return;",
            speaking_gate,
        )


    def test_stop_is_available_while_speaking(self):

        stop_index = self.service.find(
            'AddEvent(\n                            "stop"'
        )

        speaking_index = self.service.find(
            "if (isSpeaking)"
        )

        self.assertGreaterEqual(
            stop_index,
            0,
        )

        self.assertGreater(
            speaking_index,
            stop_index,
        )


    def test_native_api_uses_loopback_only(self):

        self.assertIn(
            "IPAddress.Loopback",
            self.service,
        )

        self.assertIn(
            "Port =\n            8798",
            self.service,
        )


    def test_launcher_compiles_against_system_speech(self):

        self.assertIn(
            "System.Speech",
            self.launcher,
        )

        self.assertIn(
            "JarvisVoiceService.cs",
            self.launcher,
        )


    def test_batch_starts_native_voice(self):

        self.assertIn(
            "JARVIS_NATIVE_VOICE_V32",
            self.bat,
        )

        self.assertIn(
            "start_jarvis_native_voice.ps1",
            self.bat,
        )


    def test_previous_voice_contracts_preserved(self):

        self.assertIn(
            "JARVIS_V316B2_CONVERSATIONAL_VOICE",
            self.app,
        )

        self.assertIn(
            "JARVIS_V315_VOICE_CONVERSATION",
            self.app,
        )

        self.assertIn(
            "confidence < 0.48",
            self.app,
        )

        self.assertIn(
            "+ 1600",
            self.app,
        )


    def test_javascript_syntax(self):

        node = shutil.which(
            "node"
        )

        if not node:
            self.skipTest(
                "Node.js unavailable"
            )

        result = subprocess.run(
            [
                node,
                "--check",
                str(APP),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                result.stdout
                + result.stderr
            ),
        )


    @unittest.skipUnless(
        os.name == "nt",
        "Windows-only PowerShell parser check",
    )
    def test_launcher_powershell_syntax(self):

        command = (
            "$errors=$null;"
            "[System.Management.Automation.Language.Parser]::"
            "ParseFile("
            "'C:\\\\Jarvis\\\\start_jarvis_native_voice.ps1',"
            "[ref]$null,[ref]$errors) | Out-Null;"
            "if($errors.Count -gt 0){"
            "$errors | ForEach-Object { Write-Error $_.Message };"
            "exit 1};"
            "exit 0"
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                result.stdout
                + result.stderr
            ),
        )


    @unittest.skipUnless(
        os.name == "nt",
        "Windows-only System.Speech compile check",
    )
    def test_native_service_compiles(self):

        output = (
            ROOT
            / ".jarvis-dev"
            / "JarvisVoiceService.test.exe"
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ps_source = (
            "$ErrorActionPreference='Stop';"
            "Add-Type -AssemblyName System.Speech;"
            "$speech=([System.Speech.Recognition.SpeechRecognitionEngine]).Assembly.Location;"
            "$candidates=@("
            "(Join-Path $env:WINDIR 'Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe'),"
            "(Join-Path $env:WINDIR 'Microsoft.NET\\Framework\\v4.0.30319\\csc.exe')"
            ");"
            "$csc=$candidates | Where-Object { Test-Path $_ } | Select-Object -First 1;"
            "if(-not $csc){ throw 'C# compiler not found' };"
            "& $csc /nologo /target:exe /optimize+ "
            "'/out:C:\\Jarvis\\.jarvis-dev\\JarvisVoiceService.test.exe' "
            "('/reference:' + $speech) "
            "'C:\\Jarvis\\workstation\\native_voice\\JarvisVoiceService.cs';"
            "exit $LASTEXITCODE"
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_source,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                result.stdout
                + result.stderr
            ),
        )


    def test_no_live_order_code_added(self):

        for source in (
            self.app,
            self.service,
        ):

            for token in (
                "place_order(",
                "modify_order(",
                "cancel_order(",
            ):

                self.assertNotIn(
                    token,
                    source,
                )


if __name__ == "__main__":
    unittest.main()
