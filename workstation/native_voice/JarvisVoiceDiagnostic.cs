using System;
using System.Speech.Recognition;

namespace JarvisNativeVoice
{
    public static class Program
    {
        private static SpeechRecognitionEngine recognizer;

        private static readonly string[] WakePhrases =
        {
            "jarvis",
            "hey jarvis",
            "hello jarvis",
            "hi jarvis"
        };

        private static readonly string[] StopPhrases =
        {
            "stop",
            "jarvis stop",
            "stop talking",
            "be quiet",
            "quiet"
        };

        private static bool Matches(
            string value,
            string[] choices
        )
        {
            foreach (string item in choices)
            {
                if (
                    String.Equals(
                        value,
                        item,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    return true;
                }
            }

            return false;
        }

        public static void Main()
        {
            Console.WriteLine(
                "============================================================"
            );

            Console.WriteLine(
                "JARVIS NATIVE VOICE RUNTIME - DIAGNOSTIC"
            );

            Console.WriteLine(
                "============================================================"
            );

            var installed =
                SpeechRecognitionEngine.InstalledRecognizers();

            if (
                installed == null
                || installed.Count == 0
            )
            {
                Console.WriteLine(
                    "ERROR: No Windows speech recognizer is installed."
                );

                Environment.Exit(3);
            }

            RecognizerInfo selected =
                null;

            foreach (
                RecognizerInfo info
                in installed
            )
            {
                Console.WriteLine(
                    "RECOGNIZER: "
                    + info.Culture.Name
                    + " | "
                    + info.Description
                );

                if (
                    selected == null
                    &&
                    info.Culture.Name.Equals(
                        "en-US",
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    selected =
                        info;
                }
            }

            if (
                selected == null
            )
            {
                selected =
                    installed[0];
            }

            Console.WriteLine();

            Console.WriteLine(
                "SELECTED: "
                + selected.Culture.Name
            );

            recognizer =
                new SpeechRecognitionEngine(
                    selected
                );

            Choices controls =
                new Choices();

            controls.Add(
                WakePhrases
            );

            controls.Add(
                StopPhrases
            );

            GrammarBuilder builder =
                new GrammarBuilder(
                    controls
                );

            builder.Culture =
                selected.Culture;

            Grammar grammar =
                new Grammar(
                    builder
                );

            grammar.Name =
                "jarvis-control";

            recognizer.LoadGrammar(
                grammar
            );

            recognizer.SpeechDetected +=
                delegate
                {
                    Console.WriteLine(
                        "VOICE DETECTED..."
                    );
                };

            recognizer.SpeechRecognized +=
                delegate(
                    object sender,
                    SpeechRecognizedEventArgs e
                )
                {
                    string text =
                        (
                            e.Result.Text
                            ?? ""
                        )
                        .Trim()
                        .ToLowerInvariant();

                    Console.WriteLine(
                        "HEARD: "
                        + text
                        + " | confidence="
                        + e.Result.Confidence.ToString("0.00")
                    );

                    if (
                        Matches(
                            text,
                            WakePhrases
                        )
                    )
                    {
                        Console.WriteLine(
                            ">>> WAKE WORD ACCEPTED <<<"
                        );
                    }

                    if (
                        Matches(
                            text,
                            StopPhrases
                        )
                    )
                    {
                        Console.WriteLine(
                            ">>> STOP COMMAND ACCEPTED <<<"
                        );
                    }
                };

            recognizer.SpeechRecognitionRejected +=
                delegate(
                    object sender,
                    SpeechRecognitionRejectedEventArgs e
                )
                {
                    string candidate =
                        "";

                    float confidence =
                        0;

                    if (
                        e.Result != null
                    )
                    {
                        candidate =
                            e.Result.Text
                            ?? "";

                        confidence =
                            e.Result.Confidence;
                    }

                    Console.WriteLine(
                        "REJECTED: "
                        + candidate
                        + " | confidence="
                        + confidence.ToString("0.00")
                    );
                };

            try
            {
                recognizer.SetInputToDefaultAudioDevice();
            }
            catch (
                Exception exc
            )
            {
                Console.WriteLine(
                    "MICROPHONE ERROR: "
                    + exc.Message
                );

                Environment.Exit(4);
            }

            Console.WriteLine();
            Console.WriteLine(
                "MICROPHONE: CONNECTED"
            );

            Console.WriteLine(
                "CONTROL GRAMMAR: READY"
            );

            Console.WriteLine();

            Console.WriteLine(
                "TEST 1: Say 'Jarvis'"
            );

            Console.WriteLine(
                "TEST 2: Say 'Stop'"
            );

            Console.WriteLine(
                "TEST 3: Say 'Hey Jarvis'"
            );

            Console.WriteLine(
                "TEST 4: Say 'Jarvis stop'"
            );

            Console.WriteLine();

            Console.WriteLine(
                "Press ENTER when finished."
            );

            Console.WriteLine(
                "============================================================"
            );

            recognizer.RecognizeAsync(
                RecognizeMode.Multiple
            );

            Console.ReadLine();

            try
            {
                recognizer.RecognizeAsyncCancel();
            }
            catch
            {
            }

            try
            {
                recognizer.Dispose();
            }
            catch
            {
            }

            Console.WriteLine(
                "VOICE TEST CLOSED"
            );
        }
    }
}
